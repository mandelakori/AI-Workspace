from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from aiwork.controller import Controller
from aiwork.harness import OpenCode, opencode_path
from aiwork.perception import PINS, approved_observation
from aiwork.process import environment, run
from aiwork.provider_gate import REQUIRED, catalog
from aiwork.schema import Check, Config, Profile, Task


class ScreenObservationTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.work = self.root/'work'
        self.work.mkdir()
        (self.work/'code.py').write_text('value=1\n')
        self.path = self.root/'approved.json'
        self.observation = {'schema':1,'backend':'omniparser-v2','location':'local','width':16,'height':9,
                            'cleanup_passed':True,'pins':PINS,'untrusted_screen_content':True,
                            'coordinate_system':'normalized_xyxy_image','png':'never forwarded',
                            'elements':[{'kind':'text','bbox':[0,0,.5,.5],
                                         'description':f'Example element {i}'} for i in range(13)]}
        self.path.write_text(json.dumps(self.observation),encoding='utf-8')
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.task = Task('Inspect the reviewed UI',self.work,'agent','ui',('code.py',),('code.py',),
                         (Check(('{python}','-V')),),mode='engineering',write_roots=('code.py',),
                         location='local')
        self.spec = {'workspace':str(self.work),'baseline':str(self.work),'engineering':True,
                     'objective':self.task.objective,'write_roots':['code.py'],'image':'',
                     'resources':{'operations':8,'edit_reserve':1,'verification_reserve':1},
                     'checks':[{'argv':['{python}','-V']}]}

    def test_approval_checks_hash_scope_and_freezes_bytes(self):
        owned = Profile('owned','model','http://127.0.0.1:18000/v1',engine='ollama',
                        local_calibration='reviewed.json',calibration_sha256='a'*64)
        remote = Profile('remote','model','http://127.0.0.1:18100/v1',location='a100')
        controller = Controller(Config(self.root/'state',(owned,remote)))
        for task, profile, attachment in [
                (self.task,'remote',(self.path,self.sha)),(replace(self.task,location='auto'),'owned',(self.path,self.sha)),
                (self.task,'owned',(self.path,'0'*64)),(self.task,'',(self.path,self.sha))]:
            with self.assertRaises(ValueError):
                controller.submit_task(task,True,profile_id=profile,screen=attachment)
        job = controller.submit_task(self.task,True,profile_id='owned',screen=(self.path,self.sha))
        frozen = self.root/'state'/'runs'/job
        self.assertEqual(json.loads((frozen/'intake.json').read_bytes())['screen_sha256'],self.sha)
        self.assertFalse((frozen/'baseline'/'reviewed-screen.json').exists())
        self.path.write_bytes(b'drift')
        self.assertEqual(approved_observation(frozen/'reviewed-screen.json',self.sha)[1]['sha256'],self.sha)
        (frozen/'reviewed-screen.json').write_bytes(b'drift')
        verdict = controller.run_submitted(job)
        self.assertEqual(verdict['status'],'blocked')
        self.assertIn('hash mismatch',verdict['detail'])

    def test_read_only_mcp_catalog_budget_and_pagination(self):
        def invoke(spec):
            file=self.root/'tool.json'
            file.write_text(json.dumps(spec))
            commands=[
                ('tools/list',{}),('tools/call',{'name':'screen','arguments':{'path':'private.png'}}),
                ('tools/call',{'name':'screen','arguments':{}}),
                ('tools/call',{'name':'screen','arguments':{'offset':12}})]
            requests=[{'jsonrpc':'2.0','id':i,'method':method,'params':params}
                      for i,(method,params) in enumerate(commands)]
            answer=run([sys.executable,'-m','aiwork.mcp',str(file)],Path(__file__).resolve().parents[1],10,
                       environment(self.root/'home'),stdin=('\n'.join(map(json.dumps,requests))+'\n').encode())
            self.assertEqual(answer.code,0,answer.stderr)
            return [json.loads(line)['result'] for line in answer.stdout.splitlines()]

        absent = invoke(self.spec)
        self.assertNotIn('screen',{row['name'] for row in absent[0]['tools']})
        self.assertTrue(absent[2]['isError'])
        _, approved = approved_observation(self.path,self.sha)
        result = invoke(self.spec|{'screen_observation':approved})
        self.assertIn('screen',{row['name'] for row in result[0]['tools']})
        self.assertTrue(result[1]['isError'])
        first,last = [json.loads(row['content'][0]['text']) for row in result[2:]]
        self.assertEqual((len(first['elements']),first['next_offset'],len(last['elements']),last['next_offset']),
                         (12,12,1,None))
        self.assertEqual((first['remaining_calls'],last['remaining_calls']),(7,6))
        self.assertNotIn('never forwarded',json.dumps(result))
        body = lambda names: {'tools':[{'function':{'name':n}} for n in sorted(names)]}
        self.assertFalse(catalog(body(REQUIRED|{'checks_screen'}),scoped_only=True)['passed'])
        self.assertFalse(catalog(body(REQUIRED),scoped_only=True,screen_inspection=True)['passed'])
        self.assertTrue(catalog(body(REQUIRED|{'checks_screen'}),scoped_only=True,screen_inspection=True)['passed'])

    @unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY'),'installed OpenCode with inert provider')
    def test_installed_opencode_reads_approved_screen_through_provider_gate(self):
        _, approved = approved_observation(self.path,self.sha)
        artifacts = self.root/'artifacts'
        artifacts.mkdir()
        spec = artifacts/'tool.json'
        spec.write_text(json.dumps(self.spec|{'screen_observation':approved}))
        offered, replies = [], []

        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*_):
                pass

            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                offered.append({row['function']['name'] for row in body['tools']})
                tools=[m for m in body['messages'] if m['role']=='tool']
                replies.extend(tools)
                if not tools:
                    delta={'role':'assistant','tool_calls':[{'index':0,'id':'screen_1','type':'function',
                           'function':{'name':'checks_screen','arguments':'{}'}}]}
                else:
                    delta={'role':'assistant','content':'Finished inert screen inspection'}
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.end_headers()
                for item,reason in [(delta,None),({},'stop' if tools else 'tool_calls')]:
                    chunk={'id':'screen-fixture','object':'chat.completion.chunk','model':'inert','created':1,
                           'choices':[{'index':0,'delta':item,'finish_reason':reason}]}
                    self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')

        with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
            thread=Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1')
                result=OpenCode(opencode_path()).execute(profile,self.task,self.work,artifacts,
                                                         self.task.objective,25,spec)
            finally:
                server.shutdown()
                thread.join(3)
        self.assertEqual(result.code,0,result.stderr)
        self.assertTrue(offered and all('checks_screen' in tools for tools in offered))
        self.assertIn('Example element 0',json.dumps(replies))
        self.assertNotIn('never forwarded',json.dumps(replies))
        receipt=json.loads((artifacts/'execution-receipt.json').read_bytes())
        self.assertTrue(receipt['cleanup_passed'])
        self.assertTrue(receipt['provider_gate_passed'])
