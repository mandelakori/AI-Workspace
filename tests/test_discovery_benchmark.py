"""Frozen protocol and authorization tests; no target implementation or inference."""
import json
from pathlib import Path
import tempfile
from time import monotonic
import unittest
from unittest.mock import patch

from aiwork.controller import Controller
from aiwork.discovery_benchmark import ARMS, PATHS, authorize, commands, digest, file_hash, load, milestones, order, task, upfront
from aiwork.schema import Config, Profile
from aiwork.process import Result
from aiwork.trial_budget import write
from aiwork.workspace import inventory, snapshot


class DiscoveryBenchmarkTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()
        original=self.root/'original-input';(original/'src/dotenv').mkdir(parents=True)
        (original/PATHS[0]).write_bytes(b'def unchanged(value):\n    return value\n')
        (original/'src/dotenv/main.py').write_bytes(b'def resolve_variables(values):\n    return values\n')
        (original/'FEATURE.md').write_text('A synthetic protocol objective.')
        for arm in ARMS:snapshot(original,self.root/'arms'/arm/'input',())
        (self.root/'harness.exe').write_bytes(b'inert executable identity only')
        write(self.root/'upfront-context.json',{'text':upfront(original)})
        (self.root/'validation').mkdir();write(self.root/'validation/catalog-probe.json',{'inert':True})
        self.manifest={'status':'PREPARED_NOT_AUTHORIZED','execution_allowed':False,'arms':ARMS,
            'randomization_seed':'fixed','execution_order':order('fixed'),'implementation_sha256':{'test':'hash'},
            'harness':{'path':str(self.root/'harness.exe'),'sha256':file_hash(self.root/'harness.exe')},
            'profile':{'id':'inert'},'original_inventory':inventory(original),
            'starting_inventories':{a:inventory(self.root/'arms'/a/'input') for a in ARMS},
            'context_file_sha256':file_hash(self.root/'upfront-context.json')}
        self.manifest['catalog_proof_sha256']=file_hash(self.root/'validation/catalog-probe.json')
        write(self.root/'manifest.json',self.manifest)
        (self.root/'manifest.sha256').write_text(digest(self.manifest))

    def test_order_is_deterministic_and_not_configured_by_arm_choice(self):
        self.assertEqual(order('fixed'),order('fixed'))
        self.assertEqual({tuple(order(str(i))) for i in range(32)},{('A','B'),('B','A')})

    def test_equal_clean_snapshots_tasks_and_budgets(self):
        a,b=(task(self.root,arm,self.manifest) for arm in ARMS)
        self.assertEqual(a.objective,b.objective)
        self.assertEqual(a.commands,b.commands)
        self.assertEqual(a.write_roots,PATHS)
        self.assertEqual((a.timeout,a.attempts,a.min_context),(150,1,8192))
        self.assertEqual(a.checks,(commands()[0],commands()[2]))
        self.assertEqual(self.manifest['starting_inventories']['A'],self.manifest['starting_inventories']['B'])
        a.validate();b.validate()

    def test_upfront_context_is_verbatim_bounded_and_not_an_objective_change(self):
        evidence=upfront(self.root/'original-input')
        self.assertEqual(evidence.count('def unchanged(value):\n    return value\n'),1)
        self.assertIn(file_hash(self.root/'original-input'/PATHS[0]),evidence)
        controller=Controller(Config(self.root/'controller'),initial_context=evidence)
        self.assertEqual(controller.initial_context,evidence)
        with self.assertRaises(ValueError):Controller(Config(self.root/'too-large'),initial_context='x'*8193)

    def test_controller_supplies_extra_source_once_without_changing_task_objective(self):
        evidence=upfront(self.root/'original-input')
        controller=Controller(Config(self.root/'controller'),initial_context=evidence)
        value=task(self.root,'A',self.manifest)
        attempt=self.root/'attempt';attempt.mkdir()
        with (patch('aiwork.controller.opencode_path',return_value='inert'),
              patch('aiwork.controller.Inference.ready'),
              patch.object(controller,'gpu_sample',return_value=[]),
              patch('aiwork.controller.OpenCode.execute',return_value=Result(0,0,'','',False,False)) as execute):
            controller.agent(value,Profile('inert','inert','http://127.0.0.1:1/v1',context=8192),
                             value.workspace,attempt,monotonic()+10,'',{},'')
        prompt=execute.call_args.args[4]
        self.assertEqual(prompt.count(evidence),1)
        self.assertEqual(value.objective,task(self.root,'B',self.manifest).objective)

    def test_prepared_manifest_requires_explicit_exact_grant_and_detects_drift(self):
        grant=self.root/'approval.json'
        with patch('aiwork.discovery_benchmark.implementation',return_value={'test':'hash'}):
            self.assertEqual(load(self.root)['status'],'PREPARED_NOT_AUTHORIZED')
            write(grant,{'approval_digest':digest(self.manifest),'authorize':ARMS,'operator_approved':False})
            with self.assertRaises(ValueError):authorize(self.root,grant)
            write(grant,{'approval_digest':digest(self.manifest),'authorize':['A'],'operator_approved':True})
            with self.assertRaises(ValueError):authorize(self.root,grant)
            write(grant,{'approval_digest':digest(self.manifest),'authorize':ARMS,'operator_approved':True})
            authorize(self.root,grant)
            (self.root/'arms/A/input'/PATHS[0]).write_text('changed')
            with self.assertRaisesRegex(ValueError,'arm input changed'):authorize(self.root,grant)
        self.assertFalse((self.root/'arms/A/state').exists())

    def test_implementation_or_upfront_evidence_drift_blocks_loading(self):
        with patch('aiwork.discovery_benchmark.implementation',return_value={'test':'different'}):
            with self.assertRaisesRegex(ValueError,'implementation changed'):load(self.root)
        with patch('aiwork.discovery_benchmark.implementation',return_value={'test':'hash'}):
            (self.root/'upfront-context.json').write_text('changed')
            with self.assertRaisesRegex(ValueError,'upfront evidence changed'):load(self.root)

    def test_milestones_count_only_edits_checks_and_unchanged_source_overlap(self):
        state=self.root/'measured';attempt=state/'runs/job/attempt-001';attempt.mkdir(parents=True)
        rows=[{'tool':'focus','call':1,'path':'module.py','sha256':'same','line':1,'source':'one\ntwo\n'},
              {'tool':'focus','call':2,'path':'module.py','sha256':'same','line':1,'source':'one\ntwo\n'},
              {'tool':'edit','call':3,'applied':False}, {'tool':'edit','call':4,'applied':True},
              {'tool':'check','call':5,'passed':False}]
        (attempt/'mcp.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
        write(state/'trial-budget.json',{'phases':{'work':{'started_utc':100}}})
        events=[{'part':{'tool':'checks_edit','state':{'output':'{"applied":true}','time':{'end':104000}}}},
                {'part':{'tool':'checks_check','state':{'output':'{"remaining_calls":11}','time':{'end':105000}}}}]
        (attempt/'agent.jsonl').write_text('\n'.join(json.dumps(r) for r in events))
        (attempt/'provider-response-001.sse').write_text('data: {"usage":{"prompt_tokens":120,"completion_tokens":5}}\n\ndata: [DONE]\n')
        result=milestones(state,[{'path':'module.py','sha256':'same','first':1,'last':2}])
        self.assertEqual(result['first_successful_edit_operation'],4)
        self.assertEqual(result['first_public_test_operation'],5)
        self.assertEqual(result['first_edit_seconds_from_engineering_start'],4)
        self.assertEqual(result['first_test_seconds_from_engineering_start'],5)
        self.assertEqual(result['unchanged_version_tool_overlap_lines'],2)
        self.assertEqual(result['lines_repeating_upfront_evidence'],4)
        self.assertEqual(result['first_provider_prompt_tokens'],120)
