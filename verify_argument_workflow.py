"""Exercise real models and account/session/correction persistence in an isolated database."""
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter
from unittest.mock import patch


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='results/argument_repair/workflow.json')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='argument-workflow-') as directory:
        # Set before importing the service: never open the moderator's real database.
        os.environ['DATA_DIR']=directory
        from fastapi.testclient import TestClient
        import local_dashboard as service
        with patch.dict(os.environ,{'PUBLIC_ORIGIN':'http://testserver'}), TestClient(service.app) as client:
            assert client.post('/api/auth/register',json={'name':'Workflow fixture','email':'argument-fixture@example.test','password':'temporary-fixture-pass-42'}).status_code==201
            created=client.post('/api/sessions',json={'topic':'Should schools require students to wear uniforms?'})
            assert created.status_code==201
            state=created.json();base=f'/api/sessions/{state["id"]}'
            samples=[('A','Schools should require uniforms to reduce clothing pressure.'),
                     ('B','What is the annual uniform cost?'),
                     ('A','The annual uniform cost is forty pounds.'),
                     ('B','I do not agree that a uniform policy helps every family.')]
            timings=[]
            for speaker,text in samples:
                start=perf_counter()
                response=client.post(base+'/turns',json={'speaker':speaker,'text':text,'revision':state['revision']})
                assert response.status_code==200,response.text
                state=response.json();timings.append(round((perf_counter()-start)*1000,2))
            original=state['turns'][2]['argument']
            body={'role':'claim','target':2,'relation':'answers','reason':'Moderator verified this is the intended response.','revision':4}
            reviewed=client.patch(base+'/turns/3/argument',json=body)
            assert reviewed.status_code==200,reviewed.text
            fixed=reviewed.json()
            assert fixed['turns'][2]['argument_original']==original
            assert fixed['insights']['report']['questions'][0]['status']=='moderator_answered'
            assert client.patch(base+'/turns/3/argument',json=body).status_code==409
            assert client.patch(base+'/turns/1/argument',json={**body,'revision':5,'target':3}).status_code==422
            service.sessions.clear()
            restored=client.get(base).json()
            assert restored['revision']==5
            assert restored['turns'][2]['argument_original']==original
            assert not restored['turns'][2]['argument']['link']['tentative']
            for node in restored['insights']['arguments']:
                if node['link']: assert 1<=node['link']['turn']<node['turn']
            # The frontend session export serializes this same response, including originals.
            exported=json.loads(json.dumps(restored,allow_nan=False))
            assert exported['turns'][2]['argument_original']==original
            summary={'status':'passed','scope':'Real local models, temporary SQLite, authenticated HTTP; no microphone/browser or paid API calls.',
                     'turns':len(samples),'http_turn_ms':timings,'detectors':state['detectors'],
                     'roles_before_correction':[t['argument']['role'] for t in state['turns']],
                     'checks':['real inference','account ownership','revision conflict','future-target rejection','original preserved','question moderator-confirmed','SQLite reload','JSON serialization','source integrity']}
            # Test a separate authenticated account against the same saved debate.
            with TestClient(service.app) as outsider:
                assert outsider.post('/api/auth/register',json={'name':'Other fixture','email':'other-argument@example.test','password':'temporary-fixture-pass-43'}).status_code==201
                assert outsider.get(base).status_code==404
                assert outsider.patch(base+'/turns/3/argument',json={**body,'revision':5}).status_code==404
            out=Path(__file__).resolve().parent/args.output
            out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
