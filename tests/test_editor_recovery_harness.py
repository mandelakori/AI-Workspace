"""Installed OpenCode/MCP with scripted inert provider; no inference or feature fix."""
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
from aiwork.workspace import snapshot


@unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY'),'requires installed OpenCode; inert provider only')
class EditorRecoveryHarnessTests(unittest.TestCase):
    def run_fixture(self,exhaust=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            source=b'def first(value):\r\n    return value\r\n\r\ndef second(value):\r\n    return value\r\n'
            (work/'module.py').write_bytes(source);baseline=root/'baseline';snapshot(work,baseline,())
            requests=[];errors=[]
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
                    tools={t['function']['name'] for t in body.get('tools',[])}
                    replies=[m for m in body['messages'] if m['role']=='tool']
                    done={m.get('tool_call_id') for m in replies}
                    index=sum(f'recovery_{i}' in done for i in range(9))
                    observations=[]
                    for reply in replies:
                        content=reply['content']
                        if isinstance(content,list):content=''.join(p.get('text','') for p in content)
                        try:value=json.loads(content)
                        except (ValueError,TypeError):continue
                        if value.get('source') and value.get('evidence_key'):observations.append(value)
                    seen=observations[-1] if observations else {}
                    name='checks_focus';args={'path':'module.py'};calls=[]
                    if index and index<(5 if exhaust else 9):
                        edit={'path':'module.py','expected_sha256':seen.get('sha256',''),
                              'old':'return value','new':'return value + 1','mode':'replace'}
                        if not exhaust and index in (2,6):pass
                        elif not exhaust and index==8:name='checks_check';args={'index':0}
                        else:
                            name='checks_edit';args=edit
                            if not exhaust and index==1:
                                args.update(old='def first(value):\n    return value\n',new='def first(value):\n    return value * 2\n')
                            elif not exhaust and index==7:
                                args['location']={'evidence_key':seen.get('evidence_key',''),'line':5}
                    if index<(5 if exhaust else 9):
                        if name not in tools:errors.append('required tool not advertised');self.send_error(400);return
                        calls=[{'index':0,'id':f'recovery_{index}','type':'function',
                                'function':{'name':name,'arguments':json.dumps(args)}}]
                    delta={'role':'assistant','tool_calls':calls} if calls else {'role':'assistant','content':'Scripted conformance complete.'}
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    for payload,reason in [(delta,None),({},'tool_calls' if calls else 'stop')]:
                        row={'id':'inert','object':'chat.completion.chunk','created':1,'model':'inert',
                             'choices':[{'index':0,'delta':payload,'finish_reason':reason}]}
                        self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(baseline),
                'engineering':True,'objective':'Scripted edit conformance only','write_roots':['module.py'],'image':'',
                'resources':{'operations':24,'edit_reserve':2,'verification_reserve':2,'model_requests':16},
                'checks':[{'argv':['{python}','-c','from module import first,second; assert first(3)==6; assert second(3)==4']}]}))
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1',context=8192,reasoning_effort='none')
                    task=Task('Scripted edit conformance only',work,'agent','inert',(),('module.py',),
                              (Check(('{python}','-V')),),mode='engineering',write_roots=('module.py',))
                    result=OpenCode(opencode_path()).execute(profile,task,work,artifacts,task.objective,40,spec)
                finally:server.shutdown();thread.join()
            records=[json.loads(line) for line in (artifacts/'mcp.jsonl').read_text().splitlines()]
            receipt=json.loads((artifacts/'execution-receipt.json').read_bytes())
            context=json.loads((artifacts/'execution-context.json').read_bytes())
            evidence=os.environ.get('AIWORK_TEST_EDIT_RECOVERY_EVIDENCE')
            if evidence:
                target=Path(evidence)/('exhaustion' if exhaust else 'inspect-edit-check');target.mkdir(parents=True,exist_ok=True)
                for pattern in ['execution-*.json','provider-gate.json','harness-capabilities.json','catalog-readiness.json',
                                'mcp.jsonl','edit-recovery.json','provider-request-*.json','provider-forwarded-*.json',
                                'provider-response-*.sse','source-excerpts/*.json']:
                    for path in artifacts.glob(pattern):
                        dest=target/path.relative_to(artifacts);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
                (target/'source-before.py').write_bytes(source);(target/'source-after.py').write_bytes((work/'module.py').read_bytes())
                (target/'result.json').write_bytes((json.dumps({'kind':'scripted_inert_conformance_not_autonomous_repair',
                    'harness':result.__dict__,'inert_requests':len(requests),'real_inference_requests':0,
                    'real_model_tokens':0,'controller_context':context,'receipt':receipt},indent=2)+'\n').encode())
            self.assertFalse(errors);self.assertFalse(result.timed_out,result.stderr)
            self.assertEqual(result.code,0,result.stderr);self.assertTrue(receipt['cleanup_passed'])
            self.assertTrue(receipt['provider_gate_passed'])
            self.assertEqual(context['used']['editing'],4 if exhaust else 5)
            self.assertTrue(any(r.get('code')=='repeated_edit_failure' for r in records))
            if exhaust:
                self.assertEqual(receipt['status'],'resource_exhausted');self.assertEqual(len(requests),5)
                self.assertEqual(context['used']['inference'],5)
                self.assertTrue(any(r.get('code')=='edit_recovery_exhausted' for r in records))
                self.assertEqual((work/'module.py').read_bytes(),source)
            else:
                self.assertEqual(context['used']['inspection'],3);self.assertEqual(context['used']['verification'],1)
                self.assertEqual(sum(r.get('applied',False) for r in records),2)
                self.assertTrue(any(r.get('anchor_newline_adapted') for r in records))
                self.assertTrue(records[-1]['tool']=='check' and records[-1]['passed'])
                self.assertEqual((work/'module.py').read_bytes(),source.replace(b'first(value):\r\n    return value',b'first(value):\r\n    return value * 2').replace(b'second(value):\r\n    return value',b'second(value):\r\n    return value + 1'))

    def test_inspect_eol_edit_ambiguous_recovery_location_edit_public_test(self):self.run_fixture()

    def test_repeated_edit_exhaustion_stops_inert_provider_before_next_request(self):self.run_fixture(True)
