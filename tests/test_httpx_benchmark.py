from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from time import time
from time import monotonic
from datetime import datetime, timezone
from contextlib import nullcontext
import unittest
from unittest.mock import patch

from aiwork import httpx_benchmark as benchmark
from aiwork.schema import Config, Task
from aiwork.workspace import inventory, snapshot


class BenchmarkPreparationTests(unittest.TestCase):
    def test_worker_contract_separates_preparation_without_changing_frozen_spec(self):
        path=Path(__file__).resolve().parents[1]/'examples/phase61/HTTPX-FEATURE.md'
        before=path.read_bytes()
        objective,operator=benchmark.worker_contract(before.decode())
        self.assertIn('Add path-prefix matching',objective)
        self.assertIn('normalized percent-encoded paths',objective)
        self.assertIn('tests/test_path_mounts.py',objective)
        self.assertNotIn('Preparation only',objective)
        self.assertNotIn('No model campaign is authorized',objective)
        self.assertIn('No model campaign is authorized',operator)
        self.assertIn('Independent acceptance inputs',operator)
        self.assertEqual(path.read_bytes(),before)

    def test_independent_grader_checks_exit_code_timeout_and_truncation(self):
        row={'stdout':'fixture\n','stderr':'expected error\n','code':2}
        raw={'stdout':'fixture\r\n','stderr':'expected error\r\n','code':2,'timed_out':False,'truncated':False}
        self.assertTrue(benchmark.sealed_match(row,raw))
        for patch_ in [{'code':0},{'timed_out':True},{'truncated':True},{'stderr':''}]:
            self.assertFalse(benchmark.sealed_match(row,{**raw,**patch_}))

    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name).resolve()
        source=self.root/'httpx-task'
        for name in ['httpx','tests','docs/advanced']:(source/name).mkdir(parents=True,exist_ok=True)
        (source/'FEATURE.md').write_text('Frozen public feature contract')
        (source/'_public_checks.py').write_text('class PublicPathMounts:\n def test_basic(self):pass\n def test_sync_mount_integration(self):pass\n def test_async_mount_integration(self):pass\n')
        (source/'httpx/_utils.py').write_text('# original\n')
        (source/'httpx/_client.py').write_text('# original\n')
        (source/'docs/advanced/transports.md').write_text('Original transport docs')
        snapshot(source,self.root/'httpx-input-freeze',())
        (self.root/'httpx-upstream').mkdir()
        (self.root/'local.toml').write_text('state="state"\n[[profiles]]\nid="local"\nmodel="fixture"\nendpoint="http://127.0.0.1:9999/v1"\nengine="ollama"\nreasoning_effort="none"\n')
        cfg=Config.load(self.root/'local.toml')
        review={'inventory':inventory(source),'base_commit':'pinned','write_roots':list(benchmark.PATHS),
                'feature_sha256':benchmark.file_hash(source/'FEATURE.md'),
                'public_sha256':benchmark.file_hash(source/'_public_checks.py'),
                'profile':asdict(cfg.profiles[0]),'runner':'sha256:test',
                'commands':[{'argv':['python','_public_checks.py']},{'argv':['python','-V']}]}
        import hashlib
        old=hashlib.sha256(json.dumps(review,sort_keys=True,default=str).encode()).hexdigest()
        self.review=self.root/'review.json';self.review.write_text(json.dumps({'approval_digest':old,**review}))
        self.bundle=self.root/'bundle'

    def prepare(self,**options):
        def git(args,**kwargs):return subprocess.CompletedProcess(args,0,'pinned' if args[1]=='rev-parse' else '', '')
        def probe(*args,**kwargs):return {'passed':True,'stdout':json.dumps({'timeout':'/usr/bin/timeout','utc':time()})}
        with (patch.object(benchmark.subprocess,'run',side_effect=git),
              patch.object(benchmark,'runner_status',return_value={'image_id':'sha256:test'}),
              patch.object(benchmark,'opencode_path',return_value=sys.executable),
              patch.object(benchmark,'model_metadata',return_value={'digest':'test-model'}) as model,
              patch.object(benchmark,'invoke',side_effect=probe)):
            result=benchmark.prepare(self.review,self.bundle,**options)
        self.assertEqual(model.call_count,1)  # Mocked metadata, never an inference request.
        return result

    def test_preparation_is_unauthorized_and_arms_are_identical(self):
        result=self.prepare();manifest=benchmark.load(self.bundle)
        self.assertEqual(result['status'],'PREPARED_NOT_AUTHORIZED')
        self.assertFalse(manifest['execution_allowed'])
        self.assertEqual(manifest['starting_inventories']['direct'],manifest['starting_inventories']['hierarchical'])
        self.assertEqual(sum(manifest['phase_seconds'].values()),240)
        self.assertFalse((self.bundle/'authorization.json').exists())
        self.assertNotIn('_sealed_probe.py',manifest['starting_inventories']['direct'])
        for arm in benchmark.ARMS:
            task=benchmark.task(self.bundle,arm,manifest);task.validate()
            path=self.root/(arm+'.toml');benchmark.task_file(task,path)
            self.assertEqual(Task.load(path).write_roots,benchmark.PATHS)

    def test_authorization_requires_exact_digest_and_cannot_expand_arms(self):
        result=self.prepare();grant=self.root/'grant.json'
        grant.write_text(json.dumps({'approval_digest':'wrong','authorize':list(benchmark.ARMS),'operator_approved':True}))
        with self.assertRaisesRegex(ValueError,'authorization'):benchmark.authorize(self.bundle,grant)
        grant.write_text(json.dumps({'approval_digest':result['approval_digest'],'authorize':list(benchmark.ARMS),'operator_approved':True}))
        self.assertEqual(benchmark.authorize(self.bundle,grant)['status'],'PREPARED_NOT_AUTHORIZED')

    def test_single_arm_pilot_requires_exact_scope_and_records_reviewed_budget(self):
        result=self.prepare(single_arm=True);m=benchmark.load(self.bundle)
        self.assertEqual(m['arms'],['direct'])
        self.assertEqual(m['total_seconds_approved'],240)
        self.assertEqual(m['phase_seconds'],{'warm':20,'work':180,'grade':40})
        self.assertEqual((m['worker_policy']['sessions'],m['worker_policy']['planner_requests']),(1,0))
        task=benchmark.task(self.bundle,'direct',m)
        self.assertEqual((task.attempts,task.timeout),(1,150))
        self.assertFalse((self.bundle/'arms/hierarchical').exists())
        grant=self.root/'grant.json'
        grant.write_text(json.dumps({'approval_digest':result['approval_digest'],'authorize':['direct','hierarchical'],'operator_approved':True}))
        with self.assertRaises(ValueError):benchmark.authorize(self.bundle,grant)
        grant.write_text(json.dumps({'approval_digest':result['approval_digest'],'authorize':['direct'],'operator_approved':True}))
        with patch.object(sys,'argv',['benchmark','run',str(self.bundle),'--arm','hierarchical','--authorization',str(grant)]),patch.object(benchmark,'create') as dispatch:
            with self.assertRaisesRegex(ValueError,'outside approved scope'):benchmark.main()
        dispatch.assert_not_called()

    def test_input_drift_is_rejected_before_dispatch(self):
        self.prepare()
        (self.bundle/'arms/direct/input/httpx/_utils.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'snapshot changed'):benchmark.load(self.bundle)

    def test_internal_phase_cannot_bypass_operator_gate(self):
        self.prepare()
        with patch.object(sys,'argv',['benchmark','_phase',str(self.bundle),'direct','warm']),patch.object(benchmark,'warm') as infer:
            with self.assertRaisesRegex(ValueError,'active budget lease'):benchmark.main()
        infer.assert_not_called()

    def test_cold_and_warm_starts_use_identical_neutral_request_and_worker_budget(self):
        self.prepare();manifest=benchmark.load(self.bundle)
        lease={'deadline_utc':time()+20,'deadline_monotonic':monotonic()+20}
        row={'name':'fixture','digest':'test-model','context_length':8192,
             'expires_at':datetime.fromtimestamp(time()+300,timezone.utc).isoformat()}
        cold={'resident':[]};hot={'resident':[row]}
        def fake_request(url,method,body,**kwargs):
            kwargs['capture']('request',json.dumps(body).encode())
            kwargs['capture']('response',b'{"choices":[]}')
            return {'choices':[]}
        with (patch.object(benchmark,'current',return_value=lease),
              patch.object(benchmark,'model_metadata',return_value=manifest['model']),
              patch.object(benchmark,'runner_status',return_value={'image_id':manifest['runner']}),
              patch('aiwork.router.Plane.reserve',return_value=nullcontext()),
              patch.object(benchmark,'ollama_inventory',side_effect=[cold,hot,hot,hot]),
              patch.object(benchmark,'request',side_effect=fake_request) as inference):
            for arm in benchmark.ARMS:benchmark.warm(self.bundle,arm,manifest)
        self.assertEqual(inference.call_count,2)  # Synthetic endpoints only.
        first,second=[call.args[2] for call in inference.call_args_list]
        self.assertEqual(first,second)
        self.assertEqual(first['max_tokens'],4)
        self.assertEqual(first['reasoning_effort'],'none')
        self.assertEqual(manifest['phase_seconds']['work'],180)
        self.assertEqual(manifest['phase_seconds']['warm'],20)
