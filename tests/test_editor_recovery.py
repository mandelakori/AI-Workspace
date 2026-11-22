"""Deterministic editor regressions. No model, remote endpoint or target fix."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aiwork.execution_context import ExecutionContext, ResourcePolicy, ResourceExhausted
from aiwork.mcp import inspect_source, edit_failure
from aiwork.source_edit import apply_edit, EditRejected, sha


class EditorRecoveryTests(unittest.TestCase):
    def test_all_37_preserved_proposals_on_independent_disposable_copies(self):
        from scripts.replay_source_edits import replay
        result=replay(self.root/'replay')
        self.assertEqual(result['accepted_calls'],[8,9,12,14,15,17,20,22,27,29,32])
        self.assertEqual(result['outcomes']['ambiguous_anchor'],24)
        self.assertEqual(result['proposals'],37)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.work=self.root/'work';self.work.mkdir()
        self.path=self.work/'module.py'
        self.source=b'def first(value):\r\n    return value\r\n\r\ndef second(value):\r\n    return value\r\n'
        self.path.write_bytes(self.source);self.spec=self.root/'tool.json'
        self.spec.write_text(json.dumps({'workspace':str(self.work),'baseline':str(self.work),
            'engineering':True,'objective':'Synthetic editing recovery','write_roots':['module.py'],
            'image':'','checks':[{'argv':['{python}','-V']}],
            'resources':{'operations':24,'edit_reserve':2,'verification_reserve':2}}))

    def args(self,old='return value',new='return value + 1',mode='replace',**extra):
        return {'path':'module.py','expected_sha256':sha(self.path.read_bytes()),
                'old':old,'new':new,'mode':mode,**extra}

    def edit(self,args):
        return apply_edit(self.work,('module.py',),args,self.root/'edit.lock',
                          inspections=self.root/'source-excerpts')

    def location(self,line=5,**extra):
        seen=inspect_source(self.spec,self.work,{'path':'module.py'})
        return {'evidence_key':seen['evidence_key'],'line':line,**extra}

    def reject(self,args,code):
        before=self.path.read_bytes()
        with self.assertRaises(EditRejected) as error:self.edit(args)
        self.assertEqual(error.exception.diagnostic['code'],code)
        self.assertEqual(self.path.read_bytes(),before)
        return error.exception.diagnostic

    def test_unique_multiline_lf_on_crlf_replaces_only_verified_span(self):
        old='def first(value):\n    return value\n'
        result=self.edit(self.args(old,'def first(value):\n    return value * 2\n'))
        expected=self.source.replace(old.replace('\n','\r\n').encode(),b'def first(value):\r\n    return value * 2\r\n')
        self.assertEqual(self.path.read_bytes(),expected)
        self.assertTrue(result['anchor_newline_adapted']);self.assertEqual(result['newline'],'CRLF')

    def test_crlf_on_lf_and_insertions_keep_source_convention(self):
        for source_end,proposal_end in [('\n','\r\n'),('\r\n','\n')]:
            for mode in ('replace','before','after'):
                with self.subTest(source=source_end,mode=mode):
                    before=('value = 1'+source_end+'# untouched'+source_end).encode();self.path.write_bytes(before)
                    old='value = 1'+proposal_end;new='value = 2'+proposal_end
                    r=self.edit(self.args(old,new,mode))
                    original=('value = 1'+source_end).encode();insert=('value = 2'+source_end).encode()
                    fragment=insert if mode=='replace' else insert+original if mode=='before' else original+insert
                    self.assertEqual(self.path.read_bytes(),fragment+('# untouched'+source_end).encode())
                    self.assertTrue(r['anchor_newline_adapted'])

    def test_single_line_anchor_new_multiline_and_eof_fragment(self):
        self.path.write_bytes(b'# untouched\r\nvalue = 1')
        self.edit(self.args('value = 1','value = 2\nother = 3'))
        self.assertEqual(self.path.read_bytes(),b'# untouched\r\nvalue = 2\r\nother = 3')
        self.path.write_bytes(b'value = 1')
        self.edit(self.args('1','2\nother = 3'))
        self.assertEqual(self.path.read_bytes(),b'value = 2\nother = 3')

    def test_mixed_bare_cr_and_malformed_multiline_fail_closed(self):
        for source in (b'value = 1\r\nother = 2\n',b'value = 1\rother = 2\r'):
            self.path.write_bytes(source);self.reject(self.args('1','3'),'unsupported_newlines')
        self.path.write_bytes(self.source)
        self.reject(self.args('return value','return value\r\n# mixed\n'),'unsupported_newlines')
        self.reject(self.args('first(value):\r\n    return value\n','anything'),'unsupported_newlines')
        self.reject(self.args('def first(value):\n   return value\n','anything'),'anchor_mismatch')

    def test_ambiguity_is_not_removed_by_newline_adaptation(self):
        self.reject(self.args('    return value\n','    return value * 2\n'),'ambiguous_anchor')

    def test_exact_anchor_cannot_split_crlf_and_adaptation_keeps_byte_limits(self):
        self.path.write_bytes(b'value = 1\r\n')
        self.reject(self.args('\n','\n# added\n'),'unsupported_newlines')
        self.reject(self.args('value = 1','\n'*1501),'edit_too_large')
        self.path.write_bytes(b'# comment\r\n'*110)
        self.reject(self.args('# comment\n'*110,'# replaced\n'),'edit_too_large')

    def test_grounded_location_changes_only_selected_duplicate(self):
        result=self.edit(self.args(location=self.location()))
        self.assertEqual(self.path.read_bytes(),self.source[:self.source.rindex(b'return value')]+b'return value + 1\r\n')
        self.assertEqual(result['line'],5)
        start,end=result['matched_bytes'];self.assertEqual(self.source[start:end],b'return value')

    def test_location_exact_bytes_unicode_offsets_and_eol_adaptation(self):
        self.path.write_bytes('# café\r\nvalue = 1\r\nvalue = 1\r\n'.encode())
        result=self.edit(self.args('value = 1\n','value = 2\n',location=self.location(3)))
        self.assertEqual(result['matched_bytes'],[len('# café\r\nvalue = 1\r\n'.encode()),len('# café\r\nvalue = 1\r\nvalue = 1\r\n'.encode())])
        self.assertEqual(self.path.read_bytes(),'# café\r\nvalue = 1\r\nvalue = 2\r\n'.encode())

    def test_location_requires_issued_unchanged_exact_inspection(self):
        self.reject(self.args(location={'evidence_key':'0'*64,'line':5}),'invalid_location')
        loc=self.location()
        for changed in ({'line':0},{'line':True},{'line':2,'end_line':1},{'line':99},{'extra':1}):
            self.reject(self.args(location={**loc,**changed}),'invalid_location')
        # A valid inspection cannot authorize a different original substring.
        self.reject(self.args('return missing',location=loc),'anchor_mismatch')
        self.path.write_bytes(self.source+b'# changed\r\n')
        self.reject(self.args(location=loc),'invalid_location')

    def test_forged_inspection_content_and_uninspected_lines_fail(self):
        seen=inspect_source(self.spec,self.work,{'path':'module.py','line':4})
        self.reject(self.args(location={'evidence_key':seen['evidence_key'],'line':2}),'invalid_location')
        evidence=self.root/'source-excerpts'/f"{seen['evidence_key']}.json"
        record=json.loads(evidence.read_bytes());record['source']=record['source'].replace('value','other')
        evidence.write_text(json.dumps(record))
        self.reject(self.args(location={'evidence_key':seen['evidence_key'],'line':5}),'invalid_location')

    def test_location_cannot_resolve_ambiguity_within_window_or_bypass_syntax_hash(self):
        loc=self.location(1,end_line=5)
        self.reject(self.args(location=loc),'ambiguous_anchor')
        loc={**loc,'line':5,'end_line':5}
        self.reject(self.args(new='return (',location=loc),'syntax_error')
        args=self.args(location=loc);args['expected_sha256']='0'*64
        self.reject(args,'stale_source')
        self.reject(self.args(location=loc,mode='create'),'invalid_location')

    def test_equivalent_failure_warns_then_stops_provider_and_preserves_budget(self):
        context=ExecutionContext(self.spec);context.initialize(ResourcePolicy(operations=24,edit_reserve=2,verification_reserve=2))
        for number in range(1,5):
            context.charge_tool('edit')
            args=self.args(new='different '+str(number),mode='before' if number%2 else 'replace')
            diagnostic=self.reject(args,'ambiguous_anchor')
            result=edit_failure(self.spec,self.work,('module.py',),args,diagnostic)
            self.assertEqual(result['equivalent_failures'],number)
            if number==3:
                self.assertEqual(result['code'],'repeated_edit_failure')
                inspect_source(self.spec,self.work,{'path':'module.py'})  # Does not reset.
        self.assertEqual(result['code'],'edit_recovery_exhausted')
        with self.assertRaises(ResourceExhausted):
            ExecutionContext(self.spec).provider_request({'messages':[{'role':'user','content':'continue'}]})
        self.assertEqual(context.summary()['used']['editing'],4)
        self.assertEqual(context.summary()['used']['inference'],0)
        self.assertEqual(self.path.read_bytes(),self.source)

    def test_warning_allows_different_verified_strategy_and_source_versions(self):
        args=self.args()
        for _ in range(3):edit_failure(self.spec,self.work,('module.py',),args,self.reject(args,'ambiguous_anchor'))
        self.edit(self.args(location=self.location()))
        # Changed source starts a different failure lineage; historical count retained.
        wrong=self.args('missing')
        result=edit_failure(self.spec,self.work,('module.py',),wrong,self.reject(wrong,'anchor_mismatch'))
        self.assertEqual(result['equivalent_failures'],1)
        self.assertEqual(sorted(json.loads(self.root.joinpath('edit-recovery.json').read_bytes()).values()),[1,3])

    def test_mcp_reconnect_preserves_failure_counts_and_exact_accounting(self):
        def call(name,args):
            wire=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}})+'\n'
            run=subprocess.run([sys.executable,'-m','aiwork.mcp',str(self.spec)],input=wire,
                               text=True,capture_output=True,check=True,timeout=10)
            return json.loads(json.loads(run.stdout)['result']['content'][0]['text'])
        for number in range(1,5):
            result=call('edit',self.args());self.assertEqual(result['equivalent_failures'],number)
            if number==3:self.assertTrue(call('focus',{'path':'module.py'})['source'])
        stopped=call('focus',{'path':'module.py'})
        self.assertIn('exhausted recovery',stopped['error'])
        summary=ExecutionContext(self.spec).summary()
        self.assertEqual(summary['used']['editing'],4);self.assertEqual(summary['used']['inspection'],1)
        self.assertEqual(self.path.read_bytes(),self.source)
