"""Deployment contracts use synthetic accounts, temporary DBs and a fake voice relay."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import local_dashboard as dashboard
from session_store import SessionStore, SessionConflict
from copy import deepcopy
from auth_store import AuthStore
from test_moderation_contract import resources, TOPIC


class DeploymentContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=SessionStore(Path(self.temp.name)/'database.sqlite3')
        for name,value in [('store',self.store),('auth_store',AuthStore(self.store.path)),('sessions',dashboard.OrderedDict())]:
            p=patch.object(dashboard,name,value);p.start();self.addCleanup(p.stop)
        p=patch('moderation_session.load_resources',return_value=resources());p.start();self.addCleanup(p.stop)
        self.client=TestClient(dashboard.app,base_url='https://debate.example.test')
        self.addCleanup(self.client.close)
        response=self.client.post('/api/auth/register',json={'name':'Deployment fixture','email':'deployment@example.test','password':'fixture-password-42'})
        self.assertEqual(response.status_code,201,response.text)
        self.assertIn('Secure',response.headers['set-cookie'])
        self.state=self.client.post('/api/sessions',json={'topic':TOPIC}).json()

    def test_https_owner_can_open_same_origin_wss_voice(self):
        async def relay(socket,commit):
            await socket.send_json({'type':'fixture_ready'})
            await socket.close()
        with patch.object(dashboard,'serve_voice',relay):
            with self.client.websocket_connect(f'wss://debate.example.test/api/sessions/{self.state["id"]}/voice',headers={'origin':'https://debate.example.test'}) as socket:
                self.assertEqual(socket.receive_json()['type'],'fixture_ready')

    def test_https_cross_origin_voice_is_rejected(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(f'wss://debate.example.test/api/sessions/{self.state["id"]}/voice',headers={'origin':'https://unrelated.example.test'}):
                self.fail('Cross-origin voice connection opened')

    def test_https_restart_restores_private_debate_from_database(self):
        dashboard.sessions.clear()
        response=self.client.get(f'/api/sessions/{self.state["id"]}')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['id'],self.state['id'])

    def test_canonical_origin_supports_a_tls_terminating_proxy(self):
        public='https://debate.example.test'
        async def relay(socket,commit):
            await socket.send_json({'type':'fixture_ready'})
            await socket.close()
        with patch.dict(os.environ,{'PUBLIC_ORIGIN':public}), TestClient(dashboard.app,base_url='http://internal:8080') as proxy:
            response=proxy.post('/api/auth/login',json={'email':'deployment@example.test','password':'fixture-password-42'},headers={'origin':public})
            self.assertEqual(response.status_code,200,response.text)
            self.assertIn('Secure',response.headers['set-cookie'])
            cookie=f'debate_session={proxy.cookies.get("debate_session")}'
            with patch.object(dashboard,'serve_voice',relay):
                with proxy.websocket_connect(f'ws://internal:8080/api/sessions/{self.state["id"]}/voice',headers={'origin':public,'cookie':cookie}) as socket:
                    self.assertEqual(socket.receive_json()['type'],'fixture_ready')
            denied=proxy.post('/api/auth/login',json={'email':'deployment@example.test','password':'fixture-password-42'},headers={'origin':'https://unrelated.example.test'})
            self.assertEqual(denied.status_code,403)

    def test_persistent_data_directory_can_be_configured_before_startup(self):
        env=dict(os.environ,DATA_DIR=self.temp.name)
        result=subprocess.run([sys.executable,'-c','from session_store import DEFAULT_PATH; print(DEFAULT_PATH)'],
                              env=env,text=True,capture_output=True,check=True)
        self.assertEqual(Path(result.stdout.strip()),Path(self.temp.name)/'sessions.sqlite3')

    def test_separate_worker_cache_cannot_overwrite_a_newer_saved_turn(self):
        path=f'/api/sessions/{self.state["id"]}'
        first,second=dashboard.OrderedDict(),dashboard.OrderedDict()
        with patch.object(dashboard,'sessions',first): self.client.get(path)
        with patch.object(dashboard,'sessions',second): self.client.get(path)
        with patch.object(dashboard,'sessions',first):
            saved=self.client.post(path+'/turns',json={'speaker':'A','text':'Uniform policies should protect family budgets.','revision':0})
            self.assertEqual(saved.status_code,200)
        with patch.object(dashboard,'sessions',second):
            stale=self.client.post(path+'/turns',json={'speaker':'B','text':'Uniform policies should consider clothing costs.','revision':0})
            self.assertEqual(stale.status_code,409)
        self.assertEqual(len(self.store.load(self.state['id'])['turns']),1)

    def test_database_revision_check_rejects_a_racing_writer_atomically(self):
        first=self.store.load(self.state['id'])
        second=deepcopy(first)
        first['revision']=1;first['marker']='first writer'
        second['revision']=1;second['marker']='stale writer'
        self.store.save(first,expected_revision=0)
        with self.assertRaises(SessionConflict):
            SessionStore(self.store.path).save(second,expected_revision=0)
        self.assertEqual(self.store.load(first['id'])['marker'],'first writer')


if __name__=='__main__': unittest.main()
