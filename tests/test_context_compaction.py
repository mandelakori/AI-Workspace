"""Installed OpenCode with an inert scripted provider forcing two compactions."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import Thread
import unittest

from aiwork.harness import OpenCode, opencode_path
from aiwork.schema import Check, Profile, Task


@unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY'), 'requires installed OpenCode; inert provider only')
class ContextCompactionTests(unittest.TestCase):
    def test_clean_resource_exhaustion_preserves_normalized_receipt_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            (work/'module.py').write_text('value = 1\n')
            forwarded=[]
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    forwarded.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                    delta={'role':'assistant','tool_calls':[{'index':0,'id':'read_once','type':'function',
                           'function':{'name':'checks_focus','arguments':'{"path":"module.py"}'}}]}
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    for payload,reason in [(delta,None),({},'tool_calls')]:
                        row={'id':'inert','object':'chat.completion.chunk','created':1,'model':'inert',
                             'choices':[{'index':0,'delta':payload,'finish_reason':reason}]}
                        self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Inert exhaustion check','write_roots':['module.py'],'image':'',
                'resources':{'operations':1,'edit_reserve':0,'verification_reserve':0},
                'checks':[{'argv':['{python}','-V']}]}))
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1')
                    task=Task('Inert exhaustion check',work,'agent','inert',(),('module.py',),(),
                              mode='engineering',write_roots=('module.py',))
                    result=OpenCode(opencode_path()).execute(profile,task,work,artifacts,task.objective,20,spec)
                finally:server.shutdown();thread.join()
            receipt=json.loads((artifacts/'execution-receipt.json').read_bytes())
            if os.environ.get('AIWORK_TEST_FOUNDATION_EVIDENCE'):
                target=Path(os.environ['AIWORK_TEST_FOUNDATION_EVIDENCE']).with_name('exhaustion-verified')
                target.mkdir(parents=True,exist_ok=True)
                for name in ['execution-receipt.json','execution-context.json','provider-gate.json','catalog-readiness.json']:
                    shutil.copyfile(artifacts/name,target/name)
            self.assertEqual(result.code,0,result.stderr)
            self.assertFalse(result.timed_out)
            self.assertEqual(receipt['status'],'resource_exhausted')
            self.assertNotEqual(receipt['raw_exit_code'],0)
            self.assertTrue(receipt['cleanup_passed'])
            self.assertTrue(receipt['provider_gate_passed'])
            self.assertEqual(len(forwarded),1)

    def test_two_forced_compactions_then_exact_edit_and_public_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            source=b'def calculate(value):\n    return value\n';(work/'module.py').write_bytes(source)
            fingerprint=hashlib.sha256(source).hexdigest()
            edit={'path':'module.py','expected_sha256':fingerprint,'old':'return value',
                  'new':'return value * 2','mode':'replace'}
            actions=[('checks_focus',{'path':'module.py'}),('checks_focus',{'path':'module.py'}),
                     ('checks_focus',{'path':'module.py'}),('checks_edit',edit),('checks_check',{'index':0})]
            state={'actions':0,'summaries':0};requests=[]
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    requests.append(body)
                    user=next((m.get('content','') for m in reversed(body['messages']) if m['role']=='user'),'')
                    summary=any(x in str(user).lower() for x in
                                ('summarize the conversation above','required summary template','consolidated summary'))
                    calls=[]
                    if summary:
                        state['summaries']+=1
                        delta={'role':'assistant','content':
                               '## Objective\n- Double the input.\n## Requirements\n- Use approved tools.\n'
                               '## Decisions\n- (none)\n## Work State\n### Completed\n- Inspected module.py.\n'
                               '### Active\n- Implementation.\n### Blocked\n- (none)\n'
                               '## Next Move\n1. Continue the active implementation objective.\n'
                               '## Relevant Files\n- `module.py`: implementation.\n## Important Context\n- (none)'}
                    elif state['actions']<len(actions):
                        index=state['actions'];state['actions']+=1
                        name,args=actions[index]
                        calls=[{'index':0,'id':f'action_{index}','type':'function',
                                'function':{'name':name,'arguments':json.dumps(args)}}]
                        delta={'role':'assistant','tool_calls':calls}
                    else:
                        delta={'role':'assistant','content':'Inert edit and public check complete.'}
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    # Report synthetic high context use for the first TWO inspections.
                    # The harness must really invoke its compactor, not a test mock.
                    high=not summary and 0<state['actions']<=2
                    for payload,reason in [(delta,None),({},'tool_calls' if calls else 'stop')]:
                        row={'id':'inert','object':'chat.completion.chunk','created':1,'model':'inert',
                             'choices':[{'index':0,'delta':payload,'finish_reason':reason}]}
                        if reason:
                            row['usage']={'prompt_tokens':7600 if high else 1000,'completion_tokens':50,
                                          'total_tokens':7650 if high else 1050}
                        self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Double the input','write_roots':['module.py'],'image':'',
                'resources':{'operations':24,'edit_reserve':2,'verification_reserve':2,'model_requests':16,'compactions':4},
                'checks':[{'argv':['{python}','-c','from module import calculate; assert calculate(3)==6']}]}))
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1',context=8192)
                    task=Task('Double the input',work,'agent','inert',(),('module.py',),(Check(('{python}','-V')),),
                              mode='engineering',write_roots=('module.py',))
                    result=OpenCode(opencode_path()).execute(profile,task,work,artifacts,task.objective,40,spec)
                finally:server.shutdown();thread.join()
            evidence=os.environ.get('AIWORK_TEST_FOUNDATION_EVIDENCE')
            if evidence:
                target=Path(evidence);target.mkdir(parents=True,exist_ok=True)
                for pattern in ['execution-*.json','provider-gate.json','harness-capabilities.json',
                                'catalog-readiness.json','mcp.jsonl','provider-request-*.json',
                                'provider-forwarded-*.json','provider-response-*.sse']:
                    for path in artifacts.glob(pattern):shutil.copyfile(path,target/path.name)
                (target/'result.json').write_text(json.dumps({'harness':result.__dict__,'script':state,
                    'source_sha256':hashlib.sha256((work/'module.py').read_bytes()).hexdigest()},indent=2))
            self.assertEqual(result.code,0,result.stderr)
            self.assertFalse(result.timed_out)
            self.assertEqual(state['summaries'],2)
            ledger=json.loads((artifacts/'execution-context.json').read_bytes())
            self.assertGreaterEqual(ledger['epoch'],2)
            self.assertEqual(ledger['used']['compaction'],2)
            self.assertEqual(ledger['used']['inspection'],3)
            self.assertEqual(ledger['used']['editing'],1)
            self.assertEqual(ledger['used']['verification'],1)
            records=[json.loads(line) for line in (artifacts/'mcp.jsonl').read_text().splitlines()]
            self.assertTrue(all(r.get('source') for r in records if r['tool']=='focus'))
            self.assertTrue(any(r['tool']=='check' and r['passed'] for r in records))
            self.assertIn(b'return value * 2',(work/'module.py').read_bytes())
            self.assertTrue(all('Double the input' in b['messages'][0]['content'] for b in requests))
            self.assertTrue(all([m['role'] for m in b['messages']].count('system')==1
                                and b['messages'][0]['role']=='system' for b in requests))
            self.assertTrue(json.loads((artifacts/'catalog-readiness.json').read_bytes())['cleanup_passed'])
