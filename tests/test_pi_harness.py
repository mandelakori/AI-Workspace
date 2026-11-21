"""Installed pinned Pi SDK with inert providers; never calls a real model."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import Thread, Event
from time import monotonic, sleep
import unittest

from aiwork.pi_harness import Pi, pi_path
from aiwork.process import executable
from aiwork.schema import Check, Profile, Task


@unittest.skipUnless(os.environ.get('AIWORK_TEST_PI_BOUNDARY'),'requires installed Pi SDK; inert only')
class PiHarnessTests(unittest.TestCase):
    def test_scoped_inspection_malformed_and_stale_edit_recovery_then_public_check(self):
        self.exercise()

    def test_two_actual_compactions_recover_evicted_source(self):
        self.exercise(compactions=True)

    def test_clean_resource_exhaustion_is_not_provider_failure(self):
        self.exercise(exhaust=True)

    def test_missing_catalog_fails_before_inert_backend(self):
        self.exercise(missing=True)

    def test_cancel_stream_closes_owned_job_and_relay(self):
        self.cancel()

    def test_cancel_public_check_releases_descendant_lock(self):
        self.cancel(tool=True)

    def cancel(self,tool=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            (work/'module.py').write_text('value = 1\n');stop=root/'STOP';marker=root/'started';lock=root/'owned.lock'
            arrived=Event();release=Event()
            program=("import msvcrt,time;from pathlib import Path;"
                     f"f=open({str(lock)!r},'wb');f.write(b'x');f.flush();f.seek(0);"
                     f"msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);Path({str(marker)!r}).write_text('started');time.sleep(20)")
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Inert cancellation','write_roots':['module.py'],'image':'','stop':str(stop),
                'resources':{'operations':8,'edit_reserve':0,'verification_reserve':0},
                'checks':[{'argv':['{python}','-c',program] if tool else ['{python}','-V']}]}))
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    if tool and not any(m['role']=='tool' for m in body['messages']):
                        delta={'role':'assistant','tool_calls':[{'index':0,'id':'owned_check','type':'function',
                               'function':{'name':'checks_check','arguments':'{"index":0}'}}]}
                        for payload,reason in [(delta,None),({},'tool_calls')]:
                            self.wfile.write(('data: '+json.dumps({'id':'inert','object':'chat.completion.chunk',
                                'created':1,'model':'inert','choices':[{'index':0,'delta':payload,'finish_reason':reason}]})+'\n\n').encode())
                        self.wfile.write(b'data: [DONE]\n\n');return
                    arrived.set();release.wait(12)
            def stop_owned():
                until=monotonic()+12
                while monotonic()<until:
                    if marker.exists() if tool else arrived.is_set():stop.write_text('cancel');return
                    sleep(.05)
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
                server.daemon_threads=True;thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                canceller=Thread(target=stop_owned);canceller.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1',harness='pi')
                    task=Task('Inert cancellation',work,'agent','inert',(),('module.py',),(),mode='engineering',write_roots=('module.py',))
                    sdk=pi_path(os.environ.get('AIWORK_PI_SDK',''),Path('.aiwork').resolve())
                    result=Pi(executable('node'),sdk).execute(profile,task,work,artifacts,task.objective,18,spec,stop)
                except BaseException:
                    if os.environ.get('AIWORK_TEST_PI_EVIDENCE'):
                        target=Path(os.environ['AIWORK_TEST_PI_EVIDENCE'])/('cancel-check-failed' if tool else 'cancel-stream-failed')
                        target.mkdir(parents=True,exist_ok=True)
                        for p in artifacts.iterdir():
                            if p.is_file():shutil.copyfile(p,target/p.name)
                    raise
                finally:release.set();server.shutdown();thread.join();canceller.join()
            receipt=json.loads((artifacts/'execution-receipt.json').read_bytes())
            if os.environ.get('AIWORK_TEST_PI_EVIDENCE'):
                target=Path(os.environ['AIWORK_TEST_PI_EVIDENCE'])/('cancel-check' if tool else 'cancel-stream')
                target.mkdir(parents=True,exist_ok=True)
                for name in ('execution-receipt.json','provider-gate.json','agent-live.jsonl'):
                    shutil.copyfile(artifacts/name,target/name)
            self.assertTrue(result.timed_out,result.stdout[-1000:])
            self.assertEqual(receipt['status'],'interrupted')
            self.assertTrue(receipt['cleanup_passed'])
            self.assertEqual((work/'module.py').read_text(),'value = 1\n')
            if tool:
                self.assertTrue(marker.exists())
                from aiwork.lock import file_lock
                with file_lock(lock,timeout=2):pass

    def exercise(self,compactions=False,exhaust=False,missing=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            source=b'def calculate(value):\n    return value\n';(work/'module.py').write_bytes(source)
            outside=root/'private.py';outside.write_text('PRIVATE-CANARY')
            edit={'path':'module.py','expected_sha256':hashlib.sha256(source).hexdigest(),
                  'old':'return value','new':'return value * 2','mode':'replace'}
            if compactions:
                actions=[('checks_focus',{'path':'module.py'})]*3+[('checks_edit',edit),('checks_check',{'index':0})]
            else:
                actions=[('checks_focus',{'path':'module.py'}),('checks_edit',{**edit,'old':'return (value'}),
                         ('checks_focus',{'path':'module.py'}),('checks_edit',{**edit,'expected_sha256':'0'*64}),
                         ('checks_focus',{'path':'module.py'}),('checks_edit',{**edit,'path':'../private.py'}),
                         ('checks_focus',{'path':'../private.py'}),
                         ('checks_edit',edit),('checks_check',{'index':0})]
            state={'actions':0,'summaries':0};requests=[]
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
                    summary=not body.get('tools');calls=[]
                    if summary:
                        state['summaries']+=1
                        delta={'role':'assistant','content':'## Goal\nDouble input.\n## Progress\nInspected module.py.\n## Next\nContinue approved implementation and public testing.'}
                    elif state['actions']<len(actions):
                        i=state['actions'];state['actions']+=1;name,args=actions[i]
                        calls=[{'index':0,'id':f'action_{i}','type':'function',
                                'function':{'name':name,'arguments':json.dumps(args)}}]
                        delta={'role':'assistant','tool_calls':calls}
                    else:delta={'role':'assistant','content':'Inert fixture complete.'}
                    high=compactions and not summary and 0<state['actions']<=2
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    for payload,reason in [(delta,None),({},'tool_calls' if calls else 'stop')]:
                        row={'id':'inert','object':'chat.completion.chunk','created':1,'model':'inert',
                             'choices':[{'index':0,'delta':payload,'finish_reason':reason}]}
                        if reason:row['usage']={'prompt_tokens':7600 if high else 1000,'completion_tokens':50,
                                                'total_tokens':7650 if high else 1050}
                        self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Double input','write_roots':['module.py'],'image':'',
                'resources':{'operations':1 if exhaust else 32,'edit_reserve':0,'verification_reserve':0,
                             'model_requests':16,'compactions':4},
                'checks':[] if missing else [{'argv':['{python}','-c','from module import calculate; assert calculate(3)==6']}]}))
            with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    profile=Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1',harness='pi',
                                    reasoning_effort='none',seed=1729)
                    task=Task('Double input',work,'agent','inert',(),('module.py',),(Check(('{python}','-V')),),
                              mode='engineering',write_roots=('module.py',))
                    sdk=pi_path(os.environ.get('AIWORK_PI_SDK',''),Path('.aiwork').resolve())
                    self.assertIsNotNone(sdk)
                    result=Pi(executable('node'),sdk,keep_recent_tokens=0 if compactions else 2048).execute(
                              profile,task,work,artifacts,task.objective,35,spec)
                finally:server.shutdown();thread.join()
            evidence=os.environ.get('AIWORK_TEST_PI_EVIDENCE')
            if evidence:
                target=Path(evidence)/('missing-catalog' if missing else 'compaction' if compactions else 'exhaustion' if exhaust else 'recovery')
                target.mkdir(parents=True,exist_ok=True)
                for p in artifacts.iterdir():
                    if p.is_file() and p.suffix in {'.json','.jsonl','.sse','.txt'}:shutil.copyfile(p,target/p.name)
                (target/'result.json').write_text(json.dumps({'harness':result.__dict__,'script':state},indent=2))
            self.assertFalse(result.timed_out,result.stderr)
            if missing:
                self.assertNotEqual(result.code,0);self.assertEqual(requests,[])
                self.assertTrue(json.loads((artifacts/'provider-gate.json').read_bytes())['failed_closed']);return
            self.assertEqual(result.code,0,result.stderr or result.stdout[-2000:])
            self.assertEqual(outside.read_text(),'PRIVATE-CANARY')
            self.assertNotIn('PRIVATE-CANARY',json.dumps(requests))
            receipt=json.loads((artifacts/'execution-receipt.json').read_bytes())
            self.assertTrue(receipt['cleanup_passed'])
            self.assertTrue(receipt['provider_gate_passed'])
            if exhaust:
                self.assertEqual(receipt['status'],'resource_exhausted');self.assertEqual(len(requests),1);return
            self.assertIn(b'return value * 2',(work/'module.py').read_bytes())
            records=[json.loads(line) for line in (artifacts/'mcp.jsonl').read_text().splitlines()]
            self.assertTrue(any(r['tool']=='check' and r.get('passed') for r in records))
            self.assertEqual(sum(r.get('applied',False) for r in records),1)
            self.assertTrue(all('Double input' in r['messages'][0]['content'] for r in requests))
            for request in requests:
                offered={t['function']['name'] for t in request.get('tools',[])}
                self.assertTrue(not offered or offered=={'checks_focus','checks_edit','checks_check','checks_diff'})
                self.assertEqual(request['reasoning_effort'],'none')
            if compactions:
                self.assertEqual(state['summaries'],2)
                ledger=json.loads((artifacts/'execution-context.json').read_bytes())
                self.assertEqual(ledger['used']['compaction'],2)
                self.assertGreaterEqual(ledger['epoch'],2)
                # Pi retains the last atomic tool response after the first
                # compaction. The second evicts it; only then is reinspection due.
                self.assertEqual([bool(r.get('source')) for r in records if r['tool']=='focus'],[True,False,True])
            else:
                self.assertTrue(any(r.get('code')=='stale_source' for r in records))
                self.assertTrue(any(r.get('code')=='anchor_mismatch' for r in records))
