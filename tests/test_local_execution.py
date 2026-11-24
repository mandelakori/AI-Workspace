import hashlib
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from time import monotonic
from types import SimpleNamespace

from aiwork.local_runtime import MIB, admit_context, copy_model, calibrated_runtime, isolated_ollama, load_model, startup_budget
from aiwork.process import Result
from aiwork.schema import IdleOllama,Profile,Task
from aiwork.local_calibration import capacity64


class LocalExecutionTests(unittest.TestCase):
    def test_calibrated_runtime_binds_hash_store_context_and_owned_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();store=root/'model-store';manifest=store/'manifests/registry.ollama.ai/library/inert/test'
            manifest.parent.mkdir(parents=True);manifest.write_text('{}');artifacts=root/'artifacts';artifacts.mkdir()
            report={'model':'inert','engineering_benchmark':False,'contexts':[self.row(x) for x in (8192,16384)],
                    'plan':{'gpu_headroom_mib':512},'model_copy':{'destination':str(store),
                    'manifest':'registry.ollama.ai/library/inert/test','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}}
            path=root/'calibration.json';path.write_text(json.dumps(report))
            profile=Profile('inert','inert','http://127.0.0.1:11434/v1',engine='ollama',context=32768,
                            local_calibration=str(path),calibration_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            task=Task('Scoped test',root,'agent','inert',(),(),(),context_input_tokens=7440)
            @contextmanager
            def isolated(*args,**kwargs):
                args[3].mkdir(parents=True)
                yield 'http://127.0.0.1:19999',monotonic()+300,123
            with patch('aiwork.local_runtime.memory_snapshot',return_value={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB}),\
                 patch('aiwork.local_runtime.executable',return_value='pinned-ollama'),\
                 patch('aiwork.local_runtime.isolated_ollama',side_effect=isolated) as launched,\
                 patch('aiwork.local_runtime.load_model') as preload,\
                 patch('aiwork.local_runtime.local_json',return_value={'models':[{'name':'inert','context_length':16384}]}):
                with calibrated_runtime(profile,task,artifacts,monotonic()+300) as selected:
                    self.assertEqual(selected.context,16384)
                    self.assertEqual(selected.endpoint,'http://127.0.0.1:19999/v1')
                    self.assertEqual(preload.call_args.kwargs['owner'],123)
                    self.assertEqual(preload.call_args.kwargs['context'],16384)
                    self.assertEqual(preload.call_args.kwargs['digest'],report['model_copy']['manifest_sha256'])
                self.assertEqual(profile.context,32768)
                self.assertEqual(launched.call_args.args[2],16384)
                with self.assertRaisesRegex(ValueError,'GPU free memory below'):
                    with calibrated_runtime(replace(profile,memory_mib=7800),task,artifacts,monotonic()+300):pass
                self.assertEqual(launched.call_count,1)
                with self.assertRaisesRegex(ValueError,'hash changed'):
                    with calibrated_runtime(replace(profile,calibration_sha256='0'*64),task,artifacts,monotonic()+300):pass
                reclaimed=root/'reclaimed-attempt';reclaimed.mkdir()
                policy=IdleOllama('http://127.0.0.1:11434','idle:fixture','a'*64,str(root/'ollama.exe'),'b'*64)
                before={'gpu_free_bytes':5000*MIB,'ram_available_bytes':1000*MIB}
                after={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB}
                with (patch('aiwork.local_runtime.memory_snapshot',side_effect=[before,after]) as sampler,
                      patch('aiwork.local_reclaim.reclaim_local_memory',return_value=True) as unload):
                    with calibrated_runtime(profile,task,reclaimed,monotonic()+300,idle_ollama=policy) as selected:
                        self.assertEqual(selected.context,16384)
                    self.assertEqual(sampler.call_count,2)
                    unload.assert_called_once()
                evidence=self.receipt(reclaimed,'local-context-admission')
                self.assertTrue(evidence['reclamation_rechecked'])
                self.assertEqual(evidence['memory'],after)
                preload.side_effect = TimeoutError('inert load did not reach readiness')
                failed = root/'failed-attempt'
                failed.mkdir()
                with self.assertRaisesRegex(TimeoutError, 'did not reach readiness'):
                    with calibrated_runtime(profile,task,failed,monotonic()+300):
                        self.fail('worker was released without model readiness')

    def test_calibrated_startup_retains_measured_work_and_absolute_limits(self):
        startup, stall = startup_budget(49.39, 171.923, 220)
        self.assertAlmostEqual(startup, 97.467)
        self.assertEqual(stall, 75)
        self.assertEqual(startup_budget(100, 190, 500), (120, 120))
        self.assertEqual(startup_budget(50, 160, 177), (67, 67))
        with self.assertRaises(TimeoutError):
            startup_budget(49.39, 171.923, 170)
        with self.assertRaises(ValueError):
            startup_budget(0, 172, 220)

    def test_http_readiness_and_owned_cleanup_are_independent_of_model_load(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            child = Mock(pid=123, returncode=None)
            child.poll.side_effect = lambda: child.returncode

            @contextmanager
            def owned(*args, **kwargs):
                self.assertEqual(kwargs['env']['OLLAMA_LOAD_TIMEOUT'], '75s')
                yield child
                child.returncode = 1

            with (patch('aiwork.local_runtime.owned_process', side_effect=owned),
                  patch('aiwork.local_runtime.local_json', side_effect=[OSError('not listening'), {'version': 'inert'}]) as rest,
                  patch('aiwork.local_runtime.listener_owner', return_value=123),
                  patch('aiwork.local_runtime.sleep')):
                with isolated_ollama('inert', folder, 16384, folder, monotonic()+10,
                                     load_stall_seconds=75) as (_, _, pid):
                    self.assertEqual(pid, 123)
                    self.assertTrue(self.receipt(folder, 'ownership')['ready'])
                    self.assertEqual(self.receipt(folder, 'ownership')['readiness_kind'], 'http_listener')
                    self.assertFalse((folder/'load-readiness.json').exists())
                self.assertEqual([call.args[1] for call in rest.call_args_list], ['api/version']*2)
                self.assertTrue(self.receipt(folder, 'ownership')['cleanup_passed'])

    def test_http_failure_closes_owned_process_and_failed_cleanup_is_reported(self):
        for closes in (True, False):
            with self.subTest(closes=closes), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                child = Mock(pid=123, returncode=None)
                child.poll.side_effect = lambda: child.returncode

                @contextmanager
                def owned(*args, **kwargs):
                    try:
                        yield child
                    finally:
                        child.returncode = 1 if closes else None

                with (patch('aiwork.local_runtime.owned_process', side_effect=owned),
                      patch('aiwork.local_runtime.local_json', return_value={'version':'inert'}),
                      patch('aiwork.local_runtime.listener_owner', return_value=124)):
                    message = 'not owned' if closes else 'cleanup failed'
                    with self.assertRaisesRegex(RuntimeError, message):
                        with isolated_ollama('inert', folder, 16384, folder, monotonic()+10,
                                             load_stall_seconds=75):
                            self.fail('unowned HTTP endpoint admitted')
                receipt = self.receipt(folder, 'ownership')
                self.assertFalse(receipt['ready'])
                self.assertIs(receipt['cleanup_passed'], closes)

    def test_slow_load_only_readiness_requires_exact_residency_and_charges_deadline(self):
        payload = {'load':{'model':'inert','done':True,'done_reason':'load','response':''},
                   'resident':{'models':[{'name':'inert','digest':'bound','context_length':16384}]}}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with (patch('aiwork.local_runtime.listener_owner', return_value=123),
                  patch('aiwork.local_runtime.monotonic', side_effect=[100, 101, 152, 152, 152]),
                  patch('aiwork.local_runtime.run', return_value=Result(0, 51, json.dumps(payload), '', False, False)) as client):
                load_model('http://127.0.0.1:19999','inert',16384,'bound',123,folder,175,49.39)
            self.assertAlmostEqual(client.call_args.args[2], 74)
            self.assertEqual(self.receipt(folder, 'load-readiness')['elapsed_seconds'], 52)
            self.assertTrue(self.receipt(folder, 'load-readiness')['ready'])
            self.assertEqual(self.receipt(folder, 'load-readiness')['load_requests'], 1)
            for key, stale in (('digest','wrong'), ('context_length',8192)):
                with self.subTest(key=key):
                    row = payload['resident']['models'][0]
                    wrong = payload | {'resident': {'models':[row|{key:stale}]}}
                    with (patch('aiwork.local_runtime.listener_owner', return_value=123),
                          patch('aiwork.local_runtime.run', return_value=Result(0,.01,json.dumps(wrong),'',False,False))):
                        with self.assertRaisesRegex(RuntimeError, 'identity or context'):
                            load_model('http://127.0.0.1:19999','inert',16384,'bound',123,folder,monotonic()+70,49.39)
                    self.assertFalse(self.receipt(folder, 'load-readiness')['ready'])

    def test_model_load_deadline_fails_closed_with_no_retry_or_late_release(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with (patch('aiwork.local_runtime.listener_owner', return_value=123),
                  patch('aiwork.local_runtime.run') as client):
                with self.assertRaisesRegex(TimeoutError, 'below the measured'):
                    load_model('http://127.0.0.1:19999','inert',16384,'bound',123,folder,monotonic()+40,49.39)
                client.assert_not_called()
                client.return_value = Result(1,70,'','',True,False)
                with self.assertRaisesRegex(TimeoutError, 'model readiness deadline'):
                    load_model('http://127.0.0.1:19999','inert',16384,'bound',123,folder,monotonic()+70,49.39)
                client.assert_called_once()
            self.assertFalse(self.receipt(folder, 'load-readiness')['ready'])
            self.assertEqual(self.receipt(folder, 'load-readiness')['load_requests'], 1)

    def test_owned_client_enforces_deadline_on_stalled_load_only_http_response(self):
        post_received = Event()
        release = Event()
        requests = []

        class Server(BaseHTTPRequestHandler):
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, data))
                post_received.set()
                release.wait(5)

            def do_GET(self):
                requests.append((self.path, None))

        with tempfile.TemporaryDirectory() as directory, ThreadingHTTPServer(('127.0.0.1', 0), Server) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            start = monotonic()
            try:
                with patch('aiwork.local_runtime.listener_owner', return_value=123):
                    with self.assertRaisesRegex(TimeoutError, 'model readiness deadline'):
                        load_model(f'http://127.0.0.1:{server.server_port}','inert',16384,'bound',123,
                                   Path(directory),start+1.5,.01)
                self.assertTrue(post_received.is_set())
                self.assertLess(monotonic()-start,4.0)
                self.assertEqual(requests,[('/api/generate',{'model':'inert','stream':False,
                    'keep_alive':'3m','options':{'num_ctx':16384}})])
                self.assertFalse(self.receipt(Path(directory), 'load-readiness')['ready'])
            finally:
                release.set()
                server.shutdown()
                thread.join(timeout=3)

    def receipt(self, directory, name):
        return json.loads((directory/f'{name}.json').read_bytes())

    def test_cross_plane_does_not_hide_provider_failure_or_qualify_without_mcp(self):
        examples = Path(__file__).resolve().parents[1]/'examples/native'
        with patch.object(sys, 'path', [str(examples), *sys.path]):
            import cross_plane_trial as trial
        for status, receipt, message in (
            ('blocked', {'status':'provider_failure','cleanup_passed':True}, 'provider_failure'),
            ('blocked', None, 'isolated Ollama load-only request failed'),
            ('verified', {'status':'completed','cleanup_passed':True}, 'transcript is absent'),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                attempt=root/'job/attempt-001';attempt.mkdir(parents=True)
                if receipt:
                    (attempt/'execution-receipt.json').write_text(json.dumps(receipt))
                result={'status':status,'detail':'isolated Ollama load-only request failed','artifacts':str(attempt.parent)}
                with (patch.object(trial,'config',return_value=SimpleNamespace(profiles=[None])),
                      patch.object(trial,'task'), patch.object(trial,'Controller') as controller):
                    controller.return_value.run_submitted.return_value=result
                    with self.assertRaisesRegex(RuntimeError,message):
                        trial.work(root,{})
                self.assertEqual(self.receipt(root,'engineering-result'),result)
                self.assertFalse((root/'qualified.json').exists())

    def test_local_initialization_protocol_requires_a_separate_grant(self):
        examples = Path(__file__).resolve().parents[1]/'examples/native'
        with patch.object(sys, 'path', [str(examples), *sys.path]):
            import local_initialization as probe
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approval = root/'approval.json'
            state = root/'load-only'
            manifest = {'arm':probe.ARM}
            approval.write_text(json.dumps({'approval_digest':probe.digest(manifest),
                                            'authorize':['local'],'operator_approved':True}))
            with patch.object(probe,'ROOT',state), patch.object(probe,'run_phase') as phase:
                with self.assertRaisesRegex(ValueError,'separate load-only approval'):
                    probe.run(manifest,root/'manifest.json',approval)
                self.assertFalse(state.exists())
                phase.assert_not_called()
    def test_cold_prefill_and_masked_ram_cannot_evade_admission(self):
        rows=[self.row(x) for x in (8192,16384,32768)]
        rows[1].update(ram_increment_bytes=5000*MIB,load_seconds=50,initial_prefill_overhead_seconds=48)
        rows[2].update(ram_increment_bytes=0,load_seconds=45,initial_prefill_overhead_seconds=35)
        p=dict(input_tokens=7440,output_tokens=2048,reserve_tokens=512,maximum=32768,
               memory={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB},deadline_seconds=200)
        result=admit_context({'contexts':rows},**p)
        self.assertEqual(result['selected'],16384)
        self.assertEqual(result['candidates'][2]['required_ram_bytes'],5000*MIB)
        self.assertIsNone(admit_context({'contexts':rows},**(p|{'deadline_seconds':30}))['selected'])
        self.assertIsNone(admit_context({'contexts':rows},**(p|{'memory':p['memory']|{'ram_available_bytes':6000*MIB}}))['selected'])
    def row(self,size=8192):
        return {'context':size,'status':'measured','gpu_increment_bytes':5000*MIB,
                'ram_increment_bytes':1000*MIB,'prefill_tokens_per_second':1000,
                'generation_tokens_per_second':100,'load_seconds':1}

    def test_smallest_measured_window_demand_headroom_and_deadline(self):
        report={'contexts':[self.row(x) for x in (8192,16384,32768)]}
        policy=dict(input_tokens=7440,output_tokens=2048,reserve_tokens=512,maximum=32768,
                    memory={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB},deadline_seconds=120)
        selected=admit_context(report,**policy)
        self.assertEqual(selected['selected'],16384)
        self.assertEqual(admit_context(report,**(policy|{'input_tokens':1000}))['selected'],8192)
        for change in [{'maximum':8192},{'deadline_seconds':1},{'memory':{}},
                       {'memory':{'gpu_free_bytes':5000*MIB,'ram_available_bytes':8000*MIB}},
                       {'memory':{'gpu_free_bytes':7500*MIB,'ram_available_bytes':2000*MIB}}]:
            self.assertIsNone(admit_context(report,**(policy|change))['selected'])
        report['contexts'][1]['status']='failed';report['contexts'][2]['status']='unmeasured'
        self.assertIsNone(admit_context(report,**policy)['selected'])

    def test_64k_requires_both_measured_contexts_and_resource_margin(self):
        memory={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB}
        self.assertFalse(capacity64([self.row(32768)],memory)['run'])
        rows=[self.row(16384),self.row(32768)]
        self.assertTrue(capacity64(rows,memory)['run'])
        self.assertFalse(capacity64(rows,memory|{'gpu_free_bytes':5000*MIB})['run'])
        rows[-1]['generation_tokens_per_second']=1
        self.assertFalse(capacity64(rows,memory)['run'])

    def test_model_copy_verifies_blobs_and_keeps_original_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'original';(source/'blobs').mkdir(parents=True)
            data=b'owned synthetic model bytes';digest=hashlib.sha256(data).hexdigest()
            blob=source/'blobs'/('sha256-'+digest);blob.write_bytes(data)
            name='registry.ollama.ai/library/synthetic/test'
            manifest=source/'manifests'/name;manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'config':{'digest':'sha256:'+digest,'size':len(data)},'layers':[]}))
            receipt=copy_model(source,root/'isolated',name)
            self.assertEqual(receipt['blobs']['sha256:'+digest]['sha256'],digest)
            copied=root/'isolated/blobs'/blob.name;copied.write_bytes(b'changed private copy')
            self.assertEqual(blob.read_bytes(),data)
            with self.assertRaises(ValueError):copy_model(source,root/'isolated',name)
            with self.assertRaises(ValueError):copy_model(source,root/'another','../bad')
            blob.write_bytes(b'x'*len(data))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):copy_model(source,root/'invalid',name)
