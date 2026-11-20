"""Exercise real HTTP contracts with deterministic detector fixtures and a temporary DB."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import local_dashboard as dashboard
from session_store import SessionStore
from auth_store import AuthStore
from test_moderation_contract import resources, TOPIC


class InsightsAPIContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SessionStore(Path(self.temp.name)/'sessions.sqlite3')
        self.store_patch = patch.object(dashboard,'store',self.store)
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        auth_patch=patch.object(dashboard,'auth_store',AuthStore(self.store.path))
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.memory_patch = patch.object(dashboard,'sessions',dashboard.OrderedDict())
        self.memory_patch.start()
        self.addCleanup(self.memory_patch.stop)
        self.models_patch = patch('moderation_session.load_resources',return_value=resources())
        self.models_patch.start()
        self.addCleanup(self.models_patch.stop)
        self.client=TestClient(dashboard.app)
        self.addCleanup(self.client.close)
        self.assertEqual(self.client.post('/api/auth/register',json={'name':'Fixture moderator','email':'moderator@example.test','password':'fixture-password-42'}).status_code,201)
        response=self.client.post('/api/sessions',json={'topic':TOPIC,'participants':{'A':'Maya','B':'Daniel'}})
        self.assertEqual(response.status_code,201)
        self.state=response.json()
        self.base=f'/api/sessions/{self.state["id"]}'

    def add_attack(self):
        response=self.client.post(self.base+'/turns',json={'speaker':'B','text':'You are an idiot.','revision':self.state['revision']})
        self.assertEqual(response.status_code,200)
        self.state=response.json()

    def test_create_and_list_restore_persisted_participant_names(self):
        dashboard.sessions.clear()
        state=self.client.get(self.base).json()
        self.assertEqual(state['participants']['A'],'Maya')
        self.assertEqual(self.client.get('/api/sessions').json()[0]['id'],state['id'])
        self.assertNotIn('monitor',state)
        self.assertIn('insights',state)

    def test_assessment_persists_exports_and_stale_writes_are_rejected(self):
        self.add_attack()
        route=self.base+'/alerts/R1/feedback'
        payload={'verdict':'incorrect','reason':'The model missed context.','revision':1}
        response=self.client.patch(route,json=payload)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['revision'],2)
        self.assertEqual(response.json()['alerts'][0]['status'],'Pending')
        self.assertEqual(self.client.patch(route,json=payload).status_code,409)
        dashboard.sessions.clear()
        restored=self.client.get(self.base).json()
        self.assertEqual(restored['alerts'][0]['feedback']['verdict'],'incorrect')
        exported=self.client.get(self.base+'/feedback')
        self.assertEqual(exported.status_code,200)
        self.assertIn('application/x-ndjson',exported.headers['content-type'])
        import json
        row=json.loads(exported.text)
        self.assertEqual(row['text'],'You are an idiot.')
        self.assertEqual(row['detectors']['attack'],'LinearSVC_alert')

    def test_invalid_assessment_does_not_modify_revision(self):
        self.add_attack()
        route=self.base+'/alerts/R1/feedback'
        for payload in [{'verdict':'maybe','revision':1},{'verdict':'correct','revision':1,'reason':'x'*1001}]:
            self.assertEqual(self.client.patch(route,json=payload).status_code,422)
        self.assertEqual(self.client.get(self.base).json()['revision'],1)
        self.assertEqual(self.client.patch(self.base+'/alerts/missing/feedback',json={'verdict':'correct','revision':1}).status_code,422)

    def test_measured_voice_turn_flows_into_snapshot_and_corrected_report(self):
        state=dashboard.save_turn(self.state['id'],'A','Uniform policies protect families.',source='voice',timing={
            'recording_id':'fixture', 'intervals':[{'start_ms':0,'end_ms':3500,'speaker':'A'}]})
        self.assertEqual(state['insights']['participation']['seconds']['A'],3.5)
        response=self.client.patch(self.base+'/turns/1/speaker',json={'speaker':'B'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['insights']['participation']['seconds']['B'],3.5)
        self.assertEqual(response.json()['insights']['arguments'][0]['speaker'],'B')

    def test_argument_review_is_persisted_revision_guarded_and_owner_only(self):
        for side,text in [('A','Uniforms reduce clothing costs for families.'),('B','A school survey found lower clothing costs.')]:
            self.state=self.client.post(self.base+'/turns',json={'speaker':side,'text':text,'revision':self.state['revision']}).json()
        route=self.base+'/turns/2/argument'
        body={'role':'reason','target':1,'relation':'support','reason':'Supporting estimate','revision':2}
        response=self.client.patch(route,json=body)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['turns'][1]['argument']['annotation_source'],'moderator')
        self.assertIn('argument_original',response.json()['turns'][1])
        self.assertEqual(self.client.patch(route,json=body).status_code,409)
        self.assertEqual(self.client.patch(self.base+'/turns/1/argument',json={**body,'revision':3,'target':2}).status_code,422)
        dashboard.sessions.clear()
        restored=self.client.get(self.base).json()
        self.assertFalse(restored['insights']['arguments'][1]['link']['tentative'])
        outsider=TestClient(dashboard.app)
        self.addCleanup(outsider.close)
        outsider.post('/api/auth/register',json={'name':'Other fixture','email':'other@example.test','password':'fixture-password-42'})
        self.assertEqual(outsider.patch(route,json={**body,'revision':3}).status_code,404)

    def test_voice_rejects_second_recording_for_same_moderator_before_provider(self):
        owner=self.client.get('/api/auth/me').json()['user']['id']
        with patch.object(dashboard,'voice_owners',{'other-recording':owner}), patch.object(dashboard,'voice_sessions',{'other-recording'}):
            with self.client.websocket_connect(self.base+'/voice',headers={'origin':'http://testserver'}) as socket:
                message=socket.receive_json()
                self.assertEqual(message['type'],'error')
                self.assertIn('one recording',message['message'])

    def test_voice_global_capacity_is_checked_and_reservations_release_on_error(self):
        with patch.object(dashboard,'MAX_CONCURRENT_VOICE',1), patch.object(dashboard,'voice_sessions',{'other'}), patch.object(dashboard,'voice_owners',{'other':'another-owner'}):
            with self.client.websocket_connect(self.base+'/voice',headers={'origin':'http://testserver'}) as socket:
                self.assertIn('slots',socket.receive_json()['message'])
        async def provider_error(*args):
            raise RuntimeError('Fixture upstream failure')
        with patch.object(dashboard,'serve_voice',provider_error), patch.object(dashboard,'voice_sessions',set()), patch.object(dashboard,'voice_owners',{}):
            with self.assertRaises(RuntimeError):
                with self.client.websocket_connect(self.base+'/voice',headers={'origin':'http://testserver'}) as socket:
                    socket.receive_json()
            self.assertEqual(dashboard.voice_sessions,set())
            self.assertEqual(dashboard.voice_owners,{})


if __name__=='__main__':
    unittest.main()
