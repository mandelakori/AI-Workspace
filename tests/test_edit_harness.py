"""Installed harness plus inert provider: catalog timing, scope and edit recovery."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from aiwork.harness import OpenCode, opencode_path
from aiwork.schema import Check, Profile, Task


@unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY'),'requires installed OpenCode')
class EditHarnessTests(unittest.TestCase):
    def test_missing_required_provider_tool_fails_before_inert_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            (work/'module.py').write_text('value = 1\n')
            forwarded=[]
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    forwarded.append(True);self.send_error(500)
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Synthetic readiness test','write_roots':['module.py'],'image':'','checks':[]}))
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
                thread=Thread(target=backend.serve_forever,daemon=True);thread.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{backend.server_port}/v1',context=8192)
                    task=Task('Inert readiness test.',work,'agent','inert',(),('module.py',),
                              (Check(('{python}','-V')),),mode='engineering',write_roots=('module.py',))
                    result=OpenCode(opencode_path()).execute(profile,task,work,artifacts,task.objective,15,spec)
                finally:backend.shutdown();thread.join()
            self.assertNotEqual(result.code,0)
            self.assertFalse(forwarded)
            gate=json.loads((artifacts/'provider-gate.json').read_bytes())
            self.assertTrue(gate['failed_closed'])
            self.assertTrue(all(not r['forwarded'] for r in gate['requests']))
            self.assertIn('checks_check',gate['requests'][0]['missing'])
            self.assertTrue(json.loads((artifacts/'catalog-readiness.json').read_bytes())['cleanup_passed'])
            negative=os.environ.get('AIWORK_TEST_CATALOG_NEGATIVE_EVIDENCE')
            if negative:
                Path(negative).write_bytes((json.dumps({'gate':gate,'backend_requests':len(forwarded),
                    'harness_code':result.code,'readiness':json.loads((artifacts/'catalog-readiness.json').read_bytes())},indent=2)+'\n').encode())

    def test_only_advertised_tools_are_used_and_scoped_edit_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            source=b'def calculate(value):\n    return value\n';(work/'module.py').write_bytes(source)
            outside=root/'private.py';outside.write_text('PRIVATE-CANARY')
            fingerprint=hashlib.sha256(source).hexdigest()
            edit={'path':'module.py','expected_sha256':fingerprint,'old':'return value','new':'return value * 2','mode':'replace'}
            actions=[('checks_focus',{'path':'module.py'}),
                     ('checks_edit',{**edit,'path':'../private.py'}),
                     ('checks_edit',{**edit,'expected_sha256':'0'*64}),
                     ('checks_focus',{'path':'module.py'}),('checks_edit',edit),('checks_check',{'index':0})]
            catalogs=[];replies=[];auxiliary=[];errors=[];backend_hashes=[];settings=[]
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(self):
                    self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[{"id":"inert"}]}')
                def do_POST(self):
                    raw=self.rfile.read(int(self.headers['Content-Length']))
                    backend_hashes.append(hashlib.sha256(raw).hexdigest())
                    body=json.loads(raw)
                    settings.append({k:v for k,v in body.items() if k not in {'messages','tools'}})
                    offered={t['function']['name'] for t in body.get('tools',[])}
                    if offered:catalogs.append(sorted(offered))
                    else:auxiliary.append(True)
                    messages=[m for m in body['messages'] if m['role']=='tool']
                    replies.extend(m for m in messages if m not in replies)
                    done={m.get('tool_call_id') for m in messages}
                    index=sum('source_'+str(i) in done for i in range(len(actions)))
                    calls=[]
                    if offered and index<len(actions):
                        name,args=actions[index]
                        if name in offered:identifier='source_'+str(index)
                        else:
                            errors.append('catalog unavailable');self.send_error(400);return
                        calls=[{'index':0,'id':identifier,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]
                    delta={'role':'assistant','tool_calls':calls} if calls else {'role':'assistant','content':'Inert test complete.'}
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    for payload,reason in [(delta,None),({},'tool_calls' if calls else 'stop')]:
                        row={'id':'inert','object':'chat.completion.chunk','created':1,'model':'inert','choices':[{'index':0,'delta':payload,'finish_reason':reason}]}
                        self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Double the input','write_roots':['module.py'],'image':'',
                'checks':[{'argv':['{python}','-c','from module import calculate; assert calculate(3)==6']}]}))
            with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1',context=8192,reasoning_effort='none')
                    task=Task('Double the input using only available scoped tools.',work,'agent','inert',(),('module.py',),
                              (Check(('{python}','-V')),),mode='engineering',write_roots=('module.py',))
                    result=OpenCode(opencode_path()).execute(profile,task,work,artifacts,task.objective,40,spec)
                finally:server.shutdown();thread.join()
            self.assertFalse(result.timed_out,result.stderr)
            self.assertFalse(errors)
            self.assertFalse(auxiliary)
            if os.environ.get('AIWORK_TEST_CATALOG_EVIDENCE'):
                Path(os.environ['AIWORK_TEST_CATALOG_EVIDENCE']).with_name('provider-settings.json').write_bytes((json.dumps(settings,indent=2)+'\n').encode())
            self.assertTrue(all(s.get('max_tokens',s.get('max_completion_tokens'))==2048 and s.get('reasoning_effort')=='none' for s in settings),settings)
            self.assertEqual(result.code,0,result.stderr)
            self.assertEqual(outside.read_text(),'PRIVATE-CANARY')
            self.assertIn(b'return value * 2',(work/'module.py').read_bytes())
            records=[json.loads(s) for s in (artifacts/'mcp.jsonl').read_text().splitlines() if s.strip()]
            self.assertTrue(any(r.get('code')=='stale_source' for r in records))
            self.assertTrue(any(r.get('reinspection_after_edit_error') for r in records))
            self.assertTrue(any(r.get('tool')=='check' and r['passed'] for r in records))
            self.assertEqual(sum(r.get('applied',False) for r in records),1)
            required={'checks_focus','checks_edit','checks_check','checks_diff'}
            self.assertTrue(all(required<=set(c) for c in catalogs))
            gate=json.loads((artifacts/'provider-gate.json').read_bytes())
            self.assertFalse(gate['failed_closed'])
            self.assertEqual(backend_hashes,[r['body_sha256'] for r in gate['requests']])
            self.assertTrue(json.loads((artifacts/'catalog-readiness.json').read_bytes())['cleanup_passed'])
            diagnostic=Path(os.environ.get('AIWORK_TEST_CATALOG_EVIDENCE',artifacts/'catalog-probe.json'))
            from aiwork.httpx_benchmark import implementation
            diagnostic.write_text(json.dumps({'catalogs':catalogs,'first_request_scoped_tools':sorted(set(catalogs[0])&{'checks_focus','checks_edit','checks_check','checks_diff'}),
                'native_mutation_schemas_in_first_request':sorted(set(catalogs[0])&{'edit','write','patch'}),
                'tools_issued_only_when_advertised':True,'auxiliary_requests_without_tools':len(auxiliary),
                'scoped_tools_first_present_at_agent_request':next(i for i,c in enumerate(catalogs,1) if 'checks_edit' in c),
                'result_code':result.code,'provider_gate':gate,'request_settings':settings,
                'readiness':json.loads((artifacts/'catalog-readiness.json').read_bytes()),
                'implementation_sha256':implementation()},indent=2),encoding='utf-8')
