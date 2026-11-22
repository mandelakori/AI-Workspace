"""Installed OpenCode must classify a locally truncated inert stream correctly."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from aiwork.harness import OpenCode,opencode_path
from aiwork.schema import Profile,Task,Check


@unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY'),'requires installed OpenCode, inert provider only')
class CaptureHarnessTests(unittest.TestCase):
    def test_capture_exhaustion_is_clean_resource_stop_not_provider_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            (work/'module.py').write_bytes(b'value = 1\n');received=[]
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    received.append(self.rfile.read(int(self.headers['Content-Length'])))
                    frame={'choices':[{'index':0,'delta':{'role':'assistant','content':'x'*(512*1024)},'finish_reason':None}]}
                    payload=('data: '+json.dumps(frame)+'\n\ndata: [DONE]\n\n').encode()
                    self.send_response(200);self.send_header('Content-Type','text/event-stream')
                    self.send_header('Content-Length',str(len(payload)));self.end_headers()
                    try:self.wfile.write(payload)
                    except OSError:pass
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Inert capture exhaustion','write_roots':['module.py'],'image':'',
                'resources':{'operations':24,'edit_reserve':2,'verification_reserve':2},'checks':[{'argv':['{python}','-V']}]}))
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1')
                    task=Task('Inert capture exhaustion',work,'agent','inert',(),('module.py',),
                              (Check(('{python}','-V')),),mode='engineering',write_roots=('module.py',))
                    with patch('aiwork.provider_gate.DEFAULT_CAPTURE_BYTES',256*1024):
                        result=OpenCode(opencode_path()).execute(profile,task,work,artifacts,task.objective,20,spec)
                finally:server.shutdown();thread.join()
            receipt=json.loads((artifacts/'execution-receipt.json').read_bytes());gate=json.loads((artifacts/'provider-gate.json').read_bytes())
            from aiwork.execution_context import ExecutionContext,ResourceExhausted
            with self.assertRaises(ResourceExhausted):ExecutionContext(artifacts/'opencode-tool.json').provider_request({'messages':[{'role':'user','content':'resume'}]})
            self.assertEqual(result.code,0,result.stderr);self.assertFalse(result.timed_out)
            self.assertEqual(receipt['status'],'resource_exhausted');self.assertTrue(receipt['cleanup_passed'])
            self.assertTrue(receipt['provider_gate_passed']);self.assertEqual(len(received),1)
            self.assertTrue(gate['requests'][0]['forwarded']);self.assertFalse(gate['requests'][0]['response_complete'])
            self.assertEqual(gate['captured_bytes'],256*1024);self.assertFalse(gate['failed_closed'])
            self.assertEqual((work/'module.py').read_bytes(),b'value = 1\n')
            evidence=os.environ.get('AIWORK_TEST_EVIDENCE_CAPTURE')
            if evidence:
                target=Path(evidence);target.mkdir(parents=True,exist_ok=True)
                (target/'installed-harness.json').write_bytes((json.dumps({'kind':'inert no model',
                    'harness':result.__dict__,'execution':receipt,'gate':gate},indent=2)+'\n').encode())
