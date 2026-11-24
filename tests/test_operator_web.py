from contextlib import contextmanager
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from aiwork.schema import Config, IdleOllama, Profile
from aiwork.web import Operator, bind
from aiwork.perception import PerceptionConfig


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.project = root/'project'
        self.project.mkdir()
        (self.project/'product.py').write_text('value = 0\n')
        (self.project/'public.py').write_text('print("public")\n')
        (self.project/'excluded.txt').write_text('excluded')
        self.private = root/'private'
        self.private.mkdir()
        (self.private/'accept.py').write_text('print("independent")\n')
        profiles = (Profile('laptop','local-model','http://127.0.0.1:11434/v1'),
                    Profile('existing','existing-model','http://127.0.0.1:18080/v1',location='a100'),
                    Profile('managed','cloud','http://127.0.0.1:18881/v1',location='a100',managed=True),
                    Profile('experimental','pi-model','http://127.0.0.1:17001/v1',harness='pi'))
        self.cfg = Config(root/'state', profiles, verification_image='fixture@sha256:'+'a'*64)
        self.op = Operator(self.cfg,self.project,self.private,PerceptionConfig())
        self.draft = {'objective':'Implement a new result', 'location':'auto',
                      'inputs':['product.py','public.py'], 'write_roots':['product.py'],
                      'deliverables':['product.py'], 'verification_directory':'.',
                      'checks':[{'argv':['{python}','{verification}/accept.py']}],
                      'commands':[{'argv':['{python}','public.py']}]}

    def approve(self):
        review = self.op.review(self.draft)
        return self.draft | {'review':review['review']}

    def test_review_binds_permissions_profiles_and_single_use_queue(self):
        plan = self.op.review(self.draft)
        self.assertEqual({p['profile']['id'] for p in plan['eligible']}, {'laptop','existing'})
        self.assertEqual(plan['manifest']['write_roots'],('product.py',))
        body = self.draft | {'review':plan['review']}
        with self.assertRaisesRegex(ValueError,'review'):
            self.op.queue(body | {'location':'a100'})
        job = self.op.queue(body)['job']
        self.assertTrue(self.op.jobs()['jobs'][0]['dispatchable'])
        with self.assertRaisesRegex(ValueError,'review'):
            self.op.queue(body)
        root = self.cfg.state/'runs'/job
        self.assertTrue((root/'baseline'/'product.py').is_file())
        self.assertFalse((root/'baseline'/'excluded.txt').exists())
        self.assertFalse((root/'baseline'/'accept.py').exists())
        self.assertTrue((root/'private'/'accept.py').is_file())

    def test_permission_rejections(self):
        for changes in ({'workspace':'../private'}, {'inputs':[]}, {'commands':[]},
                        {'write_roots':['.git']}, {'write_roots':['public.py']}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.op.review(self.draft | changes)
        with self.assertRaisesRegex(ValueError,'verification image'):
            Operator(Config(self.cfg.state),self.project,None,PerceptionConfig()).review(self.draft)
        with self.assertRaisesRegex(ValueError,'separate'):
            Operator(self.cfg,self.project,self.project,PerceptionConfig())
        with self.assertRaisesRegex(ValueError,'enrollment'):
            self.op.reclaim({'confirm':True})

    def test_dispatch_requires_session_owned_queued_job(self):
        job = self.op.queue(self.approve())['job']
        fresh = Operator(self.cfg,self.project,self.private,PerceptionConfig())
        with self.assertRaisesRegex(ValueError,'this web session'):
            fresh.run({'job':job})
        with patch.object(self.op.controller,'run_submitted') as run:
            self.assertEqual(self.op.run({'job':job})['dispatch'],'accepted')
            with self.op.dispatch:
                run.assert_called_once_with(job)
            with self.assertRaises(ValueError):
                self.op.run({'job':job})

    def test_artifact_previews_exclude_private_cases_and_raw_provider_content(self):
        job = self.op.queue(self.approve())['job']
        attempt = self.cfg.state/'runs'/job/'attempt-01'
        attempt.mkdir()
        (attempt/'proposed.patch').write_text('diff --git a/product.py b/product.py')
        (attempt/'check-00.json').write_text(json.dumps(
            {'passed':True,'total':2,'passed_cases':2,'cases':['private sentinel'],'stdout':'private sentinel'}))
        (attempt/'agent-metrics.json').write_text('{"tokens":{"input":3,"output":2}}')
        (attempt/'execution-receipt.json').write_text('{"resources":{"limits":{}},"raw":"private sentinel"}')
        (attempt/'provider-response.bin').write_text('private sentinel')
        result = self.op.detail(job)['attempts'][0]
        self.assertIn('diff --git',result['patch'])
        self.assertEqual(result['verification'][0]['passed_cases'],2)
        self.assertEqual(result['metrics']['tokens']['input'],3)
        self.assertNotIn('private sentinel',json.dumps(result))

    def test_confirmed_memory_reclamation_reserves_lane_and_resamples(self):
        policy = IdleOllama('http://127.0.0.1:11434','model:tag','a'*64, 'ollama.exe','b'*64)
        from dataclasses import replace
        op = Operator(replace(self.cfg,idle_ollama=policy),self.project,self.private,PerceptionConfig())
        with self.assertRaisesRegex(ValueError,'confirmation'):
            op.reclaim({'confirm':'true'})
        with patch('aiwork.web.reclaim_local_memory',return_value=True) as reclaim, patch(
                'aiwork.web.memory_snapshot',side_effect=[{'free':3},{'free':7}]):
            result = op.reclaim({'confirm':True})
        self.assertEqual((result['before'],result['after']),({'free':3},{'free':7}))
        self.assertIs(reclaim.call_args.args[0],policy)

    @contextmanager
    def server(self):
        with bind(self.op,0) as server:
            worker = Thread(target=server.serve_forever,daemon=True)
            worker.start()
            try:
                yield server.server_port
            finally:
                server.shutdown()
                worker.join(3)

    def test_loopback_routes_assets_and_csrf_gate(self):
        with self.server() as port, patch('aiwork.web.capture_screen',return_value=b'frame') as capture:
            host = f'127.0.0.1:{port}'
            def request(method, path, **headers):
                conn = HTTPConnection('127.0.0.1',port,timeout=3)
                try:
                    conn.request(method,path,b'{}' if method=='POST' else None,headers)
                    response = conn.getresponse()
                    return response.status,response.read(),dict(response.headers)
                finally:
                    conn.close()
            code,html,headers = request('GET','/')
            self.assertEqual(code,200)
            self.assertIn(self.op.session.encode(),html)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
            self.assertEqual(request('GET','/app.js')[0],200)
            self.assertEqual(request('GET','/api/jobs',Host='attacker.invalid')[0],403)
            self.assertEqual(request('GET','/private/accept.py')[0],404)
            valid = {'Origin':'http://'+host,'X-AIWork-Session':self.op.session,'Content-Type':'application/json'}
            for denied in ({}, valid | {'Origin':'https://attacker.invalid'}, valid | {'X-AIWork-Session':'bad'}):
                self.assertEqual(request('POST','/api/capture',**denied)[0],403)
            capture.assert_not_called()
            self.assertEqual(json.loads(request('POST','/api/capture',**valid)[1]),{'png':'ZnJhbWU='})
            capture.assert_called_once()


if __name__=='__main__':
    unittest.main()
