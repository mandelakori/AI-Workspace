"""Final-trial contracts, offline public baseline and admission; never inference."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aiwork.httpx_benchmark import digest,file_hash,implementation
from aiwork.schema import Config,Check
from aiwork.verify import invoke
from aiwork.workspace import snapshot,inventory

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('final_acceptance_trial',ROOT/'examples/milestone-e-final/trial.py')
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


class FinalAcceptanceTests(unittest.TestCase):
    def fixture(self,root):
        source=ROOT/'.aiwork/a100-readiness/upstream-itsdangerous'
        snapshot(source,root/'source',());snapshot(root/'source',root/'input',())
        for src,dst in [('FEATURE.md','FEATURE.md'),('PUBLIC-VERIFICATION.md','PUBLIC-VERIFICATION.md'),('checks.py','_aiwork_checks.py'),
                        ('original_checks.py','_aiwork_original_checks.py'),('public-cases.json','_aiwork_public.json'),('expanded-cases.json','_aiwork_expanded.json')]:
            (root/'input'/dst).write_bytes((trial.ASSETS/src).read_bytes())
        (root/'input/_aiwork_contract.json').write_text(json.dumps({'original_doc_sha256':inventory(root/'source')['docs/timed.rst']['sha256']}))
        binary=root/'opencode';binary.write_bytes(b'inert never executed')
        profile=Config.load(trial.ASSETS/'controller.toml').profiles[0]
        (root/'evaluation-exclusions.json').write_text(json.dumps({'fingerprints':[]}))
        m={'kind':'milestone-e-final-itsdangerous','arm':trial.ARM,'phase_limits':trial.LIMITS,'worker':deepcopy(trial.WORKER),'public_protocol':deepcopy(trial.PUBLIC),
            'profile':asdict(profile),'permissions':{'write_paths':list(trial.PATHS)},'request_options':trial.request_options(profile),
            'endpoint_identity':{'model_path':profile.model},'input_inventory':inventory(root/'input'),'pristine_inventory':inventory(root/'source'),
            'runner':'sha256:inert','opencode':{'path':str(binary),'sha256':file_hash(binary)},'implementation_sha256':implementation(),
            'asset_hashes':{p.name:file_hash(p) for p in trial.ASSETS.iterdir() if p.is_file()},
            'evaluation_exclusions_sha256':file_hash(root/'evaluation-exclusions.json'),
            'capture_policy':{'payload_bytes':67108864,'disk_headroom_bytes':33554432,'metadata_bytes':16777216,'request_attribution_limit':1024},
            'execution_state':str(root/'execution'),'ssh':{'alias':'inert','remote_port':1}}
        self.save(root,m);return m

    def save(self,root,m):
        (root/'manifest.json').write_text(json.dumps(m));(root/'manifest.sha256').write_text(digest(m))

    def test_original_feature_cases_and_verifier_are_byte_identical(self):
        for new,old in [('FEATURE.md','FEATURE.md'),('public-cases.json','public-cases.json'),('original_checks.py','checks.py')]:
            self.assertEqual((trial.ASSETS/new).read_bytes(),(ROOT/'examples/milestone-e-a100'/old).read_bytes())
        cases=json.loads((trial.ASSETS/'expanded-cases.json').read_bytes())
        self.assertEqual(len(cases),36);self.assertEqual(len({row['id'] for row in cases}),36)
        self.assertTrue(all(row['expanded'] is True for row in cases))
        self.assertTrue(any(abs(row.get('seconds',0))>2**53 for row in cases))

    def test_every_gate_and_completed_worker_required_for_freeze(self):
        candidate={'passed_cases':48,'original_passed':12,'gates':{k:True for k in trial.ACTIONS[:-1]},'all_gates_passed':True}
        receipt={'status':'completed','cleanup_passed':True};decision={'accepted':True};calls=[{'tool':'edit','applied':True},{'tool':'check','index':7,'passed':True}];result={'status':'verified'}
        self.assertTrue(trial.qualified(candidate,receipt,decision,calls,result))
        for gate in candidate['gates']:
            bad=deepcopy(candidate);bad['gates'][gate]=False
            self.assertFalse(trial.qualified(bad,receipt,decision,calls,result),gate)
        for bad in [{'status':'resource_exhausted','cleanup_passed':True},{'status':'provider_failure','cleanup_passed':True},{'status':'completed','cleanup_passed':False}]:
            self.assertFalse(trial.qualified(candidate,bad,decision,calls,result))
        self.assertFalse(trial.qualified(candidate,receipt,decision,calls[1:],result))
        self.assertFalse(trial.qualified(candidate,receipt,decision,calls[:1],result))
        self.assertFalse(trial.qualified(candidate,receipt,decision,calls,{'status':'failed'}))

    def test_incomplete_work_is_retained_without_freeze_or_grade(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);m=self.fixture(root);m['baseline']={}
            a=root/'state/runs/inert/attempt-001';a.mkdir(parents=True)
            (a/'execution-receipt.json').write_text(json.dumps({'status':'completed','cleanup_passed':True}))
            (a/'mcp.jsonl').write_text(json.dumps({'tool':'check','index':7,'passed':False})+'\n')
            candidate={'passed_cases':48,'original_passed':12,'gates':{k:True for k in trial.ACTIONS[:-1]},'all_gates_passed':False};candidate['gates']['documentation']=False
            with patch.object(trial,'Controller') as controller,patch.object(trial,'evaluate',return_value=candidate),patch.object(trial,'compare',return_value={'accepted':True,'reason':'improved'}):
                controller.return_value.run_submitted.return_value={'status':'failed'}
                trial.work(root,m)
            self.assertTrue((root/'engineering-incomplete.json').exists());self.assertFalse((root/'frozen').exists());self.assertFalse((root/'frozen.json').exists())
            self.assertFalse(json.loads((root/'selection.json').read_bytes())['decision']['accepted'])
            with self.assertRaises((ValueError,FileNotFoundError)):trial.closed(root)

    def test_freshness_keys_ignore_cosmetic_fields_and_equivalent_durations(self):
        a={'api':'signer','age':3,'delta':{'seconds':1},'id':'fixture-only','expected':{}}
        b={**a,'id':'changed','message':'cosmetic','delta':{'microseconds':1000000}}
        self.assertEqual(trial.fingerprint(a),trial.fingerprint(b))
        zero={**a,'delta':{'seconds':0}};self.assertEqual(trial.fingerprint(zero),trial.fingerprint({**zero,'delta':{'microseconds':-0.0}}))
        self.assertNotEqual(trial.fingerprint(a),trial.fingerprint({**a,'age':4}))
        with self.assertRaises(ValueError):trial.fingerprint({**a,'age':.5})
        exclusions=json.loads((trial.ASSETS/'diagnostic-exclusions.json').read_bytes())
        self.assertEqual(len(exclusions['fingerprints']),38)
        self.assertIn(trial.fingerprint({'api':'signer','age':0,'delta':{'seconds':0}}),exclusions['fingerprints'])

    def test_approval_and_resource_input_drift_fail_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);m=self.fixture(root);self.assertEqual(trial.load(root),m)
            grant=root/'grant.json';grant.write_text(json.dumps({'approval_digest':digest(m),'authorize':[trial.ARM],'operator_approved':False}))
            with patch.object(trial,'run_phase') as dispatch:
                with self.assertRaises(ValueError):trial.run(root,grant)
                dispatch.assert_not_called()
            for key,value in [('operations',97),('model_requests',65)]:
                bad=deepcopy(m);bad['worker'][key]=value;self.save(root,bad)
                with self.assertRaisesRegex(ValueError,'resource/public/scope'):trial.load(root)
            self.save(root,m);(root/'input/FEATURE.md').write_text('stale')
            with self.assertRaisesRegex(ValueError,'source changed'):trial.load(root)

    def test_task_retains_limits_and_presents_active_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);m=self.fixture(root);task=trial.task(root,m);task.validate()
            self.assertEqual((task.timeout,task.attempts,task.tool_operations,task.model_requests,task.compaction_limit),(720,1,96,64,4))
            self.assertEqual((task.edit_reserve,task.public_test_reserve),(8,8));self.assertEqual(len(task.commands),8)
            self.assertEqual(task.checks[0].argv[-1],'acceptance');self.assertIn('Command indices',task.objective)
            self.assertFalse((root/'input/diagnostic-exclusions.json').exists());self.assertFalse((root/'input/case_identity.py').exists())

    def test_verification_cannot_promote_mutated_workspace_even_with_claimed_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);m=self.fixture(root)
            results={k:{'passed':True} for k in trial.ACTIONS[:-1]}
            results['public_original'].update(passed_cases=12)
            results['public_expanded'].update(passed_cases=48,cases=[{'passed':True} for _ in range(48)])
            def tamper(check,work,*args):
                (work/'_aiwork_public.json').write_text('changed during verification')
                return {'passed':True,'stdout':json.dumps({'results':results})}
            with patch.object(trial,'invoke',side_effect=tamper):value=trial.evaluate(root,root/'input',root/'candidate',m)
            self.assertFalse(value['verification_workspace_unchanged']);self.assertFalse(value['all_gates_passed'])

    @unittest.skipUnless(os.environ.get('AIWORK_TEST_DOCKER_IMAGE'),'requires existing offline Docker')
    def test_authored_failures_retain_actionable_assertions_without_operator_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            path=root/'input/tests/test_itsdangerous/test_timedelta_max_age.py'
            path.write_text('import pytest\n@pytest.mark.parametrize("n",range(6))\ndef test_fixture_failure(n):\n    assert False, "DIAGNOSTIC_ASSERTION_CANARY"\n')
            result=invoke(Check(('python','_aiwork_checks.py','authored'),timeout=45),root/'input',root/'home',
                'sha256:00d3d7e3d1e32064b5bf313cc788fb91945c0c5fa000856513f490f2c8087645')
            self.assertFalse(result['passed']);value=json.loads(result['stdout'])
            self.assertTrue(all(row['failures'] and 'DIAGNOSTIC_ASSERTION_CANARY' in row['failures'][0]['message'] for row in value['runs']))
            self.assertIn('DIAGNOSTIC_ASSERTION_CANARY',value['summary'])

    @unittest.skipUnless(os.environ.get('AIWORK_TEST_DOCKER_IMAGE'),'requires existing offline Docker')
    def test_authored_verifier_accepts_parametrized_pristine_unit_fixture_and_rejects_sleeps(self):
        # Verifier unit fixture only, never copied to the real trial. It tests the
        # pristine API's missing-feature behavior; it is not a feature solution.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root);path=root/'input/tests/test_itsdangerous/test_timedelta_max_age.py'
            path.write_text('''import pytest
from datetime import timedelta
from itsdangerous import TimestampSigner
@pytest.mark.parametrize("n", range(6))
def test_pristine_reference(n):
    s=TimestampSigner("unit-fixture")
    with pytest.raises(TypeError): s.unsign(s.sign(b"x"),max_age=timedelta(seconds=n))
@pytest.mark.parametrize("v", [None,2**80])
def test_original_numeric(v):
    s=TimestampSigner("unit-fixture")
    assert s.unsign(s.sign(b"x"),max_age=v)==b"x"
def test_original_type_rejection():
    s=TimestampSigner("unit-fixture")
    with pytest.raises(TypeError): s.unsign(s.sign(b"x"),max_age={})
''')
            image='sha256:00d3d7e3d1e32064b5bf313cc788fb91945c0c5fa000856513f490f2c8087645'
            result=invoke(Check(('python','_aiwork_checks.py','authored'),timeout=45),root/'input',root/'home',image)
            self.assertTrue(result['passed'],result);data=json.loads(result['stdout']);self.assertTrue(all(r['tests_passed']==9 for r in data['runs']))
            for statement in ['import time as clock; clock.sleep(0)','from time import sleep as nap; nap(0)']:
                path.write_text(statement+'\nassert True\n')
                result=invoke(Check(('python','_aiwork_checks.py','authored'),timeout=45),root/'input',root/'home',image)
                self.assertFalse(result['passed']);self.assertIn('wall-clock sleep',result['stdout'])

    @unittest.skipUnless(os.environ.get('AIWORK_TEST_DOCKER_IMAGE'),'requires existing offline Docker')
    def test_real_clean_source_reproduces_separate_original_and_expanded_baselines(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            result=invoke(Check(('python','_aiwork_checks.py','acceptance'),timeout=45),root/'input',root/'home',
                'sha256:00d3d7e3d1e32064b5bf313cc788fb91945c0c5fa000856513f490f2c8087645')
            self.assertFalse(result['passed']);data=json.loads(result['stdout']);results=data['results']
            self.assertEqual(results['public_original']['passed_cases'],3);self.assertEqual(results['public_expanded']['passed_cases'],22)
            self.assertEqual(results['public_expanded']['total'],48);self.assertTrue(results['upstream']['passed']);self.assertTrue(results['syntax']['passed'])
            self.assertFalse(results['authored']['passed']);self.assertFalse(results['documentation']['passed']);self.assertFalse(results['interfaces']['passed'])
