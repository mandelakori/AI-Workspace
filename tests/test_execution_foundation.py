"""Deterministic controller contracts; no model inference or benchmark fixtures."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from time import time
import unittest
from unittest.mock import patch

from aiwork.context_planning import ContextMeasurements, plan_context
from aiwork.execution_context import ExecutionContext, ResourceExhausted, ResourcePolicy
from aiwork.harness import QwenCode
from aiwork.harness_contracts import admit
from aiwork.mcp import inspect_source
from aiwork.schema import Profile, Task


class ExecutionFoundationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.spec = self.root/'tool.json'
        self.spec.write_text(json.dumps({'objective':'Double the input', 'write_roots':['module.py'],
                                         'checks':[{'argv':['approved-public-check']}],
                                         'deadline':time()+60}))
        self.context = ExecutionContext(self.spec)
        self.context.initialize(ResourcePolicy(operations=12, edit_reserve=2, verification_reserve=2))

    def request(self, *values):
        return {'model':'inert', 'messages':[{'role':'user','content':'Continue'}, *[
            {'role':'tool','content':json.dumps(v)} for v in values]], 'tools':[]}

    def test_two_evictions_recover_exact_source_without_resetting_budget(self):
        (self.root/'module.py').write_text('value = 1\n', newline='\n')
        for epoch in range(3):
            self.context.charge_tool('focus')
            value = inspect_source(self.spec, self.root, {'path':'module.py'})
            self.assertEqual(value['context_epoch'], epoch)
            self.assertEqual(value['source'], 'value = 1\n')
            forwarded, trace = self.context.provider_request(self.request(value))
            self.assertIn('Double the input', forwarded['messages'][0]['content'])
            self.assertEqual(trace['remaining_operations'], 11-epoch)
            self.assertTrue(inspect_source(self.spec,self.root,{'path':'module.py'})['already_inspected'])
            if epoch < 2:
                summary = self.request()
                summary['messages'][0]['content'] = 'context checkpoint; original source evicted'
                self.context.provider_request(summary)
        self.context.charge_tool('edit')
        self.context.charge_tool('check')
        with self.context.state() as s:
            self.assertEqual(s['used']['inspection'],3)
            self.assertEqual(s['used']['compaction'],2)
            self.assertEqual(s['epoch'],2)
            self.assertEqual(self.context.remaining(s),7)

    def test_reservations_reconnect_and_clean_exhaustion(self):
        for _ in range(8): self.context.charge_tool('focus')
        with self.assertRaisesRegex(ResourceExhausted,'reserved'): self.context.charge_tool('diff')
        for _ in range(2): self.context.charge_tool('edit')
        for _ in range(2): self.context.charge_tool('check')
        reopened = ExecutionContext(self.spec)
        reopened.initialize(ResourcePolicy(operations=12,edit_reserve=2,verification_reserve=2))
        with self.assertRaisesRegex(ResourceExhausted,'exhausted'): reopened.provider_request(self.request())
        with self.assertRaisesRegex(ResourceExhausted,'exhausted'): reopened.charge_tool('focus')

    def test_unproductive_reads_stop_without_spending_reserved_operations(self):
        for _ in range(8): self.context.charge_tool('focus')
        for _ in range(3):
            with self.assertRaises(ResourceExhausted): self.context.charge_tool('focus')
        with self.assertRaisesRegex(ResourceExhausted,'unproductive'): self.context.provider_request(self.request())

    def test_contract_change_deadline_and_model_budget_fail_closed(self):
        value = json.loads(self.spec.read_bytes());value['objective']='Changed scope'
        self.spec.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'contract changed'): self.context.initialize(ResourcePolicy())
        with self.context.state() as s: s['contract']['deadline']=time()-1
        with self.assertRaisesRegex(ResourceExhausted,'deadline'): self.context.provider_request(self.request())

    def test_compaction_and_model_calls_are_bounded_independently(self):
        with self.context.state() as s: s['contract']['policy']['model_requests']=2
        self.context.provider_request(self.request())
        self.context.provider_request(self.request())
        with self.assertRaisesRegex(ResourceExhausted,'model request'): self.context.provider_request(self.request())

    def test_summaries_cannot_claim_source_visibility(self):
        (self.root/'module.py').write_text('value = 1\n')
        value=inspect_source(self.spec,self.root,{'path':'module.py'})
        self.context.provider_request(self.request(value))
        body=self.request();body['messages'].append({'role':'assistant','content':json.dumps(value)})
        self.context.provider_request(body)
        with self.context.state() as s: self.assertEqual(s['visible'],[])

    def test_capability_admission_blocks_qwen_before_process_or_provider(self):
        receipt=admit('opencode',self.root)
        self.assertTrue(receipt['admitted'])
        task=Task('Implement',self.root,'agent','fixture',(),(),(),mode='engineering')
        profile=Profile('inert','inert','http://127.0.0.1:1/v1',harness='qwen')
        with patch('aiwork.harness.run') as run:
            with self.assertRaisesRegex(ValueError,'exact_hash_editor'):
                QwenCode(['never-run']).execute(profile,task,self.root,self.root,'Implement',1,self.spec)
            run.assert_not_called()
        self.assertFalse(json.loads((self.root/'harness-capabilities.json').read_bytes())['admitted'])

    def test_production_policy_is_configurable_and_not_sixteen(self):
        task=Task('Implement',self.root,'agent','fixture',(),(),())
        self.assertEqual(task.tool_operations,48)
        for kwargs in [{'operations':True}, {'operations':4}, {'edit_reserve':-1}, {'model_requests':0}]:
            with self.assertRaises(ValueError): ResourcePolicy(**kwargs)


class ContextPlanningTests(unittest.TestCase):
    def measurements(self):
        return ContextMeasurements('synthetic','synthetic test, not hardware',32768,
                                   8*2**30,32*2**30,5*2**30,2*2**30,32768,.75,1000,40)

    def plan(self,m=None,**changes):
        policy=dict(candidates=(8192,16384,32768),hard_max=32768,input_tokens=9000,
                    output_tokens=1000,reserve_tokens=500,deadline_seconds=60)
        return plan_context(m or self.measurements(),**(policy|changes))

    def test_smallest_feasible_window_can_exceed_8k_without_maximizing(self):
        plan=self.plan();self.assertEqual(plan['selected'],16384);self.assertFalse(plan['applied'])
        self.assertEqual(self.plan(input_tokens=4000)['selected'],8192)

    def test_memory_offload_deadline_and_model_maximum_can_reject(self):
        self.assertIsNone(self.plan(replace(self.measurements(),available_vram_bytes=1))['selected'])
        self.assertIsNone(self.plan(replace(self.measurements(),available_ram_bytes=1))['selected'])
        self.assertIsNone(self.plan(deadline_seconds=1)['selected'])
        self.assertIsNone(self.plan(replace(self.measurements(),supported_max=8192))['selected'])
        self.assertIsNone(self.plan(hard_max=8192)['selected'])

    def test_missing_or_nonfinite_measurements_fail_closed(self):
        for changes in [{'provenance':''},{'kv_bytes_per_token':0}, {'prefill_tokens_per_second':float('nan')}]:
            with self.assertRaises(ValueError):replace(self.measurements(),**changes)
