"""Preparation/authorization guards only: never dispatch model workers."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aiwork.harness_comparison import ARMS,LIMITS,authorize,closed,load,run
from aiwork.httpx_benchmark import digest,file_hash,implementation
from aiwork.schema import Profile
from aiwork.trial_budget import create,FILE
from aiwork.workspace import inventory


class HarnessComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();source=self.root/'original-input';source.mkdir()
        (source/'module.py').write_text('value = 1\n')
        for arm in ARMS:
            work=self.root/'arms'/arm/'input';work.mkdir(parents=True);(work/'module.py').write_text('value = 1\n')
        self.binary=self.root/'binary';self.binary.write_bytes(b'pinned binary')
        self.calibration=self.root/'calibration.json';self.calibration.write_text('{}')
        (self.root/'initial-context.json').write_text('{}')
        self.manifest={'kind':'local-harness-pair','arms':ARMS,'phase_limits':LIMITS,
            'implementation_sha256':implementation(),'pi':{'path':str(self.root),'runtime_sha256':{}},
            'opencode':{'path':str(self.binary),'sha256':file_hash(self.binary)},
            'calibration':{'path':str(self.calibration),'sha256':file_hash(self.calibration)},
            'initial_context_sha256':file_hash(self.root/'initial-context.json'),
            'original_inventory':inventory(source),'starting_inventories':{a:inventory(self.root/'arms'/a/'input') for a in ARMS},
            'profiles':{a:asdict(Profile('local-'+a,'inert','http://127.0.0.1:1/v1',harness=a)) for a in ARMS},
            'runner':'sha256:synthetic'}
        self.save()
        self.stub=patch('aiwork.harness_comparison.runtime_hashes',return_value={});self.stub.start();self.addCleanup(self.stub.stop)

    def save(self):
        (self.root/'manifest.json').write_text(json.dumps(self.manifest))
        (self.root/'manifest.sha256').write_text(digest(self.manifest))

    def test_exact_authorization_is_required_and_false_grant_never_dispatches(self):
        approval=self.root/'grant.json'
        for grant in ({'approval_digest':digest(self.manifest),'authorize':ARMS,'operator_approved':False},
                      {'approval_digest':'0'*64,'authorize':ARMS,'operator_approved':True},
                      {'approval_digest':digest(self.manifest),'authorize':['pi'],'operator_approved':True}):
            approval.write_text(json.dumps(grant))
            with patch('aiwork.harness_comparison.run_phase') as dispatch:
                with self.assertRaises(ValueError):run(self.root,approval)
                dispatch.assert_not_called()
            self.assertFalse((self.root/'execution-started.json').exists())
        approval.write_text(json.dumps({'approval_digest':digest(self.manifest),'authorize':ARMS,'operator_approved':True}))
        self.assertEqual(authorize(self.root,approval),self.manifest)

    def test_frozen_inputs_runtime_and_matching_parameters_detect_drift(self):
        self.assertEqual(load(self.root),self.manifest)
        (self.root/'arms/pi/input/module.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'arm input'):load(self.root)
        (self.root/'arms/pi/input/module.py').write_text('value = 1\n')
        self.manifest['profiles']['pi']['context']=16384;self.save()
        with self.assertRaisesRegex(ValueError,'unmatched'):load(self.root)

    def test_consumed_comparison_and_unfrozen_candidates_cannot_resume_or_grade(self):
        approval=self.root/'grant.json';approval.write_text(json.dumps({'approval_digest':digest(self.manifest),
                    'authorize':ARMS,'operator_approved':True}))
        (self.root/'execution-started.json').write_text('{}')
        with patch('aiwork.harness_comparison.runner_status',return_value={'image_id':'sha256:synthetic'}),\
             patch('aiwork.harness_comparison.run_phase') as dispatch:
            with self.assertRaisesRegex(ValueError,'consumed'):run(self.root,approval)
            dispatch.assert_not_called()
        with self.assertRaises((ValueError,FileNotFoundError)):closed(self.root)

    def test_larger_caps_are_explicit_and_do_not_change_historical_defaults(self):
        with self.assertRaises(ValueError):create(self.root/'old','old','direct',LIMITS)
        create(self.root/'new','new','pi',LIMITS,reviewed_caps=LIMITS,quotas={'sessions':1,'planner_requests':0})
        data=json.loads((self.root/'new'/FILE).read_bytes())
        self.assertEqual(data['reviewed_phase_caps'],LIMITS)
        self.assertEqual(data['phases']['work']['limit'],330)
        self.assertEqual(data['sessions'],0)
