"""Account persistence, cookie lifecycle and access isolation, using temporary data only."""
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi import HTTPException
from contextlib import closing
from starlette.websockets import WebSocketDisconnect
from auth_store import AuthStore, AuthError, hash_password, verify_password
from session_store import SessionStore
import local_dashboard as dashboard
from test_moderation_contract import resources, TOPIC

PASSWORD='fixture-password-only-42'


class PasswordContracts(unittest.TestCase):
    def test_password_hash_is_salted_and_verifies_only_the_right_password(self):
        first,second=hash_password(PASSWORD),hash_password(PASSWORD)
        self.assertNotEqual(first,second)
        self.assertNotIn(PASSWORD,first)
        self.assertTrue(verify_password(PASSWORD,first))
        self.assertFalse(verify_password('wrong-password',first))
        self.assertFalse(verify_password(PASSWORD,'malformed'))


class AccountAccessContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'workspace.sqlite3'
        self.store=SessionStore(self.path)
        self.auth=AuthStore(self.path)
        for target,value in [('store',self.store),('auth_store',self.auth),('sessions',dashboard.OrderedDict())]:
            p=patch.object(dashboard,target,value);p.start();self.addCleanup(p.stop)
        p=patch('moderation_session.load_resources',return_value=resources());p.start();self.addCleanup(p.stop)
        self.client=TestClient(dashboard.app,base_url='http://127.0.0.1:7863')
        self.other=TestClient(dashboard.app,base_url='http://127.0.0.1:7863')
        self.addCleanup(self.client.close);self.addCleanup(self.other.close)

    def register(self,client,email='alice@example.test'):
        response=client.post('/api/auth/register',json={'name':'Fixture User','email':email,'password':PASSWORD,'remember':True})
        self.assertEqual(response.status_code,201,response.text)
        return response

    def debate(self,client):
        response=client.post('/api/sessions',json={'topic':TOPIC})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def test_anonymous_api_and_workspace_are_protected(self):
        self.assertTrue(self.client.get('/api/auth/me').json()['setup_required'])
        self.assertEqual(self.client.get('/api/sessions').status_code,401)
        self.assertEqual(self.client.post('/api/sessions',json={'topic':TOPIC}).status_code,401)
        response=self.client.get('/app/',follow_redirects=False)
        self.assertEqual(response.status_code,303)
        self.assertTrue(response.headers['location'].startswith('/login'))

    def test_registration_persists_and_cookie_is_http_only(self):
        response=self.register(self.client,'Alice@Example.Test')
        cookie=response.headers['set-cookie']
        self.assertIn('HttpOnly',cookie)
        self.assertIn('SameSite=lax',cookie)
        self.assertIn('Max-Age=',cookie)
        user=self.client.get('/api/auth/me').json()['user']
        self.assertEqual(user['email'],'alice@example.test')
        token=self.client.cookies.get('debate_session')
        self.assertEqual(AuthStore(self.path).user_for_token(token)['id'],user['id'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertNotIn(PASSWORD,db.execute('SELECT password_hash FROM users').fetchone()[0])
            self.assertNotEqual(token,db.execute('SELECT token_hash FROM login_sessions').fetchone()[0])
        self.assertEqual(self.other.post('/api/auth/register',json={'name':'Duplicate','email':'alice@example.test','password':PASSWORD}).status_code,409)

    def test_login_rejects_wrong_password_logout_revokes_cookie(self):
        self.register(self.client)
        first_token=self.client.cookies.get('debate_session')
        self.client.post('/api/auth/logout')
        self.assertIsNone(self.auth.user_for_token(first_token))
        self.assertEqual(self.client.get('/api/sessions').status_code,401)
        bad=self.client.post('/api/auth/login',json={'email':'alice@example.test','password':'wrong-password'})
        self.assertEqual(bad.status_code,401)
        good=self.client.post('/api/auth/login',json={'email':'ALICE@example.test','password':PASSWORD,'remember':False})
        self.assertEqual(good.status_code,200)
        self.assertNotIn('Max-Age=',good.headers['set-cookie'])
        self.assertTrue(self.client.get('/api/auth/me').json()['user'])

    def test_other_account_cannot_read_mutate_export_or_open_voice_for_cached_debate(self):
        self.register(self.client)
        state=self.debate(self.client)
        path=f'/api/sessions/{state["id"]}'
        self.register(self.other,'bob@example.test')
        self.assertEqual(self.other.get('/api/sessions').json(),[])
        self.assertEqual(self.other.get(path).status_code,404)
        self.assertEqual(self.other.post(path+'/turns',json={'speaker':'A','text':'Uniforms help families.','revision':0}).status_code,404)
        self.assertEqual(self.other.patch(path+'/alerts/R1/feedback',json={'verdict':'correct','revision':0}).status_code,404)
        self.assertEqual(self.other.get(path+'/feedback').status_code,404)
        with self.assertRaises(WebSocketDisconnect):
            with self.other.websocket_connect('ws://127.0.0.1:7863'+path+'/voice',headers={'origin':'http://127.0.0.1:7863'}):
                self.fail('Other user connected to private voice session')
        self.assertEqual(self.client.get(path).status_code,200)

    def test_first_account_adopts_legacy_data_once(self):
        from moderation_session import new_session
        legacy=new_session(TOPIC,resources());legacy['revision']=0
        self.store.save(legacy)
        self.register(self.client)
        self.assertEqual(self.client.get('/api/sessions').json()[0]['id'],legacy['id'])
        self.register(self.other,'bob@example.test')
        self.assertEqual(self.other.get('/api/sessions').json(),[])
        self.assertEqual(self.store.load(legacy['id'])['owner_id'],self.client.get('/api/auth/me').json()['user']['id'])

    def test_expired_and_forged_tokens_do_not_authenticate(self):
        self.register(self.client)
        self.assertIsNone(self.auth.user_for_token('made-up-token'))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE login_sessions SET expires_at=?',(time.time()-1,))
        self.assertEqual(self.client.get('/api/sessions').status_code,401)

    def test_cross_origin_auth_requests_are_rejected_and_failures_are_limited(self):
        payload={'name':'Test','email':'alice@example.test','password':PASSWORD}
        self.assertEqual(self.client.post('/api/auth/register',json=payload,headers={'origin':'https://unrelated.example'}).status_code,403)
        self.register(self.client)
        statuses=[self.other.post('/api/auth/login',json={'email':'alice@example.test','password':'wrong-password'}).status_code for _ in range(7)]
        self.assertIn(429,statuses)

    def test_user_inputs_are_validated(self):
        for payload in [dict(name='A',email='invalid',password=PASSWORD),dict(name='A',email='a@b.test',password='short')]:
            self.assertEqual(self.client.post('/api/auth/register',json=payload).status_code,422)

    def test_authenticated_voice_commits_for_owner_and_rechecks_revoked_login(self):
        self.register(self.client)
        state=self.debate(self.client)
        token=self.client.cookies.get('debate_session')
        async def relay(socket,commit):
            saved=commit('A','Uniforms help families.',None)
            await socket.send_json({'type':'fixture_saved','turns':len(saved['turns'])})
            self.auth.revoke(token)
            with self.assertRaises(HTTPException) as caught:
                commit('B','Uniform costs should be considered.',None)
            self.assertEqual(caught.exception.status_code,401)
            await socket.close()
        with patch.object(dashboard,'serve_voice',relay):
            with self.client.websocket_connect(f'ws://127.0.0.1:7863/api/sessions/{state["id"]}/voice',headers={'origin':'http://127.0.0.1:7863'}) as socket:
                self.assertEqual(socket.receive_json()['turns'],1)
        self.assertEqual(len(self.store.load(state['id'])['turns']),1)


if __name__=='__main__': unittest.main()
