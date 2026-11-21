import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from aiwork.source_edit import apply_edit, EditRejected


class SourceEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.path=self.root/'module.py'
        self.path.write_bytes(b'def calculate(value):\n    return value\n')
        self.lock=self.root/'edit.lock'

    def args(self,old='return value',new='return value * 2',mode='replace'):
        return {'path':'module.py','expected_sha256':hashlib.sha256(self.path.read_bytes()).hexdigest(),
                'old':old,'new':new,'mode':mode}

    def apply(self,args,**kwargs):return apply_edit(self.root,('module.py','new.py'),args,self.lock,**kwargs)

    def test_multiline_mismatch_is_explicit_and_short_exact_replacement_recovers(self):
        source=b'def calculate(value):\n    if value < 0:\n        raise ValueError(\n            "negative"\n        )\n    return value\n'
        self.path.write_bytes(source)
        args=self.args('        raise ValueError(\n            "negative")','raise Exception()')
        with self.assertRaises(EditRejected) as caught:self.apply(args)
        self.assertEqual(caught.exception.diagnostic['code'],'anchor_mismatch')
        self.assertEqual(caught.exception.diagnostic['focus_arguments']['line'],3)
        self.assertEqual(self.path.read_bytes(),source)
        result=self.apply(self.args())
        self.assertEqual(result['before_sha256'],hashlib.sha256(source).hexdigest())
        self.assertIn(b'return value * 2',self.path.read_bytes())

    def test_stale_hash_and_ambiguous_overlapping_anchors_never_write(self):
        args=self.args();self.path.write_bytes(b'def calculate(value):\n    return value + 1\n')
        before=self.path.read_bytes()
        with self.assertRaises(EditRejected) as caught:self.apply(args)
        self.assertEqual(caught.exception.diagnostic['code'],'stale_source')
        self.assertEqual(self.path.read_bytes(),before)
        self.path.write_bytes(b'# aaaa\ndef calculate(value):\n    return value\n')
        before=self.path.read_bytes()
        with self.assertRaises(EditRejected) as caught:self.apply(self.args('aa','x'))
        self.assertEqual(caught.exception.diagnostic['code'],'ambiguous_anchor')
        self.assertEqual(caught.exception.diagnostic['anchor_matches'],3)
        self.assertEqual(self.path.read_bytes(),before)

    def test_contextual_insert_preserves_crlf_and_indentation(self):
        source=b'def calculate(value):\r\n    return value\r\n';self.path.write_bytes(source)
        self.apply(self.args('    return value\r\n','    if value is None:\r\n        return 0\r\n','before'))
        self.assertEqual(self.path.read_bytes(),b'def calculate(value):\r\n    if value is None:\r\n        return 0\r\n    return value\r\n')
        with self.assertRaises(EditRejected):self.apply(self.args('    return value\n','bad'))

    def test_syntax_scope_size_and_deadline_failures_preserve_bytes(self):
        source=self.path.read_bytes()
        with self.assertRaises(EditRejected) as caught:self.apply(self.args('    return value','  return value\n        pass'))
        self.assertEqual(caught.exception.diagnostic['code'],'syntax_error')
        args=self.args();args['path']='../outside.py'
        with self.assertRaises(ValueError):self.apply(args)
        (self.root/'tests.py').write_text('protected')
        args=self.args();args['path']='tests.py'
        with self.assertRaises(ValueError):self.apply(args)
        with self.assertRaises(EditRejected):self.apply(self.args(new='x'*3001))
        with self.assertRaises(EditRejected):self.apply(self.args(),deadline=0)
        self.assertEqual(self.path.read_bytes(),source)
        self.assertEqual((self.root/'tests.py').read_text(),'protected')

    def test_noop_is_not_reported_as_an_applied_edit(self):
        before=self.path.read_bytes()
        with self.assertRaises(EditRejected) as caught:self.apply(self.args(new='return value'))
        self.assertEqual(caught.exception.diagnostic['code'],'no_change')
        self.assertEqual(self.path.read_bytes(),before)

    def test_concurrent_source_change_is_not_overwritten_and_temporary_is_removed(self):
        original=tempfile.NamedTemporaryFile;changed=b'def calculate(value):\n    return 99\n'
        def race(*args,**kwargs):
            self.path.write_bytes(changed)
            return original(*args,**kwargs)
        args=self.args()
        with patch('aiwork.source_edit.tempfile.NamedTemporaryFile',side_effect=race):
            with self.assertRaises(EditRejected):self.apply(args)
        self.assertEqual(self.path.read_bytes(),changed)
        self.assertEqual(list(self.root.glob('.aiwork-edit-*')),[])

    def test_create_is_exclusive_and_mode_is_preserved_for_replacement(self):
        mode=self.path.stat().st_mode
        self.apply(self.args())
        self.assertEqual(self.path.stat().st_mode,mode)
        args={'path':'new.py','expected_sha256':'absent','old':'','new':'value = 1\n','mode':'create'}
        self.apply(args);self.assertEqual((self.root/'new.py').read_bytes(),b'value = 1\n')
        with self.assertRaises(EditRejected):self.apply(args)
        self.assertEqual((self.root/'new.py').read_bytes(),b'value = 1\n')

    def test_competing_creator_is_never_overwritten(self):
        operation='rename' if os.name=='nt' else 'link'
        original=getattr(os,operation)
        def competing(src,dst):
            Path(dst).write_bytes(b'competing creator\n')
            original(src,dst)
        args={'path':'new.py','expected_sha256':'absent','old':'','new':'value = 1\n','mode':'create'}
        with patch('aiwork.source_edit.os.'+operation,side_effect=competing):
            with self.assertRaises(EditRejected):self.apply(args)
        self.assertEqual((self.root/'new.py').read_bytes(),b'competing creator\n')
        self.assertFalse(list(self.root.glob('.aiwork-edit-*')))

    def test_mcp_recovery_refresh_and_public_test_sequence(self):
        spec=self.root/'tool.json'
        spec.write_text(json.dumps({'workspace':str(self.root),'baseline':str(self.root),
            'engineering':True,'objective':'Double the input','write_roots':['module.py'],
            'image':'','checks':[{'argv':['{python}','-c','from module import calculate; assert calculate(3)==6']}]}))
        # Keep artifacts outside the source workspace, as in production.
        work=self.root/'work';work.mkdir();(work/'module.py').write_bytes(self.path.read_bytes())
        config=json.loads(spec.read_bytes());config.update(workspace=str(work),baseline=str(work));spec.write_text(json.dumps(config))
        good=self.args();bad={**good,'expected_sha256':'0'*64}
        messages=[('focus',{'path':'module.py'}),('edit',bad),('focus',{'path':'module.py'}),('edit',good),('check',{'index':0})]
        wire='\n'.join(json.dumps({'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':n,'arguments':a}}) for i,(n,a) in enumerate(messages))+'\n'
        p=subprocess.run([sys.executable,'-m','aiwork.mcp',str(spec)],input=wire,capture_output=True,text=True,check=True,timeout=20)
        rows=[json.loads(json.loads(s)['result']['content'][0]['text']) for s in p.stdout.splitlines()]
        self.assertEqual(rows[1]['code'],'stale_source')
        self.assertTrue(rows[2]['reinspection_after_edit_error'])
        self.assertTrue(rows[2]['source'])
        self.assertTrue(rows[3]['applied'])
        self.assertTrue(rows[4]['passed'])
        self.assertEqual(rows[4]['remaining_calls'],11)
