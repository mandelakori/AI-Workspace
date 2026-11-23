"""Installed inert OpenCode can see and call the final trial's acceptance menu."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest
import test_final_acceptance as final
from aiwork.harness import OpenCode,opencode_path
from aiwork.schema import Profile
trial=final.trial


@unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY') and os.environ.get('AIWORK_TEST_DOCKER_IMAGE'),'installed OpenCode and existing offline Docker; inert only')
class FinalHarnessTests(unittest.TestCase):
    def test_64k_final_contract_and_acceptance_index_are_available_before_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();m=final.FinalAcceptanceTests().fixture(root);work=root/'input';artifacts=root/'artifacts';artifacts.mkdir()
            task=trial.task(root,m);requests=[]
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
                    tools={t['function']['name'] for t in body['tools']}
                    assert {'checks_check','checks_focus','checks_edit','checks_diff'}<=tools
                    done=any(row.get('tool_call_id')=='final_acceptance_fixture' for row in body['messages'])
                    calls=[] if done else [{'index':0,'id':'final_acceptance_fixture','type':'function','function':{'name':'checks_check','arguments':'{"index":7}'}}]
                    delta={'role':'assistant','tool_calls':calls} if calls else {'role':'assistant','content':'Inert contract fixture finished; no engineering claim.'}
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    for value,reason in [(delta,None),({},'tool_calls' if calls else 'stop')]:
                        self.wfile.write(('data: '+json.dumps({'choices':[{'index':0,'delta':value,'finish_reason':reason}]})+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
            image='sha256:00d3d7e3d1e32064b5bf313cc788fb91945c0c5fa000856513f490f2c8087645'
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),'engineering':True,'objective':task.objective,
                'write_roots':list(task.write_roots),'image':image,'checks':[{'argv':list(c.argv),'timeout':c.timeout} for c in task.commands],
                'resources':{'operations':96,'edit_reserve':8,'verification_reserve':8,'model_requests':64,'compactions':4}}))
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    profile=replace(Profile(**m['profile']),endpoint=f'http://127.0.0.1:{server.server_port}/v1')
                    result=OpenCode(opencode_path()).execute(profile,task,work,artifacts,task.objective,40,spec)
                finally:server.shutdown();thread.join()
            self.assertEqual(result.code,0,result.stderr);self.assertFalse(result.timed_out)
            self.assertTrue(all(body.get('max_tokens',body.get('max_completion_tokens'))==4096 and body['temperature']==0 and body['seed']==1729 and body['chat_template_kwargs']=={'enable_thinking':False} for body in requests))
            rows=[json.loads(line) for line in (artifacts/'mcp.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['index'],7);self.assertFalse(rows[0]['passed']);self.assertIn('Mandatory gates',rows[0]['stdout'])
            self.assertTrue(json.loads((artifacts/'execution-receipt.json').read_bytes())['cleanup_passed'])
            evidence=os.environ.get('AIWORK_TEST_FINAL_HARNESS_EVIDENCE')
            if evidence:
                target=Path(evidence);target.mkdir(parents=True,exist_ok=True)
                for name in ['mcp.jsonl','mcp-catalog.json','provider-gate.json','execution-receipt.json','catalog-readiness.json','execution-context.json']:
                    (target/name).write_bytes((artifacts/name).read_bytes())
                (target/'result.json').write_bytes((json.dumps({'kind':'INERT; no model inference or autonomous feature claim','harness':result.__dict__,'fake_requests':len(requests)},indent=2)+'\n').encode())
