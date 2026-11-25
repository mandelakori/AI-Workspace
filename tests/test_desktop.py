import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from aiwork.desktop import Desktop
from aiwork.perception import PerceptionConfig
from aiwork.schema import Config, Profile


class DesktopTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.project = self.root/'code'
        self.project.mkdir()
        (self.project/'logic.py').write_text('def add(a,b): return a+b\n')
        (self.project/'.env').write_text('SENSITIVE_CANARY')
        tests = self.project/'tests'
        tests.mkdir()
        (tests/'test_logic.py').write_text('import unittest\n')
        profiles = (
            Profile('local','test-model','http://127.0.0.1:11434/v1'),
            Profile('remote','test-large','http://127.0.0.1:18100/v1',location='a100'),
        )
        self.config = Config(self.root/'state',profiles,verification_image='fixture@sha256:'+'a'*64)
        self.desktop = Desktop(self.config,self.project,PerceptionConfig())
        self.desktop.runtime = {'ready':True,'detail':'fixture'}
        self.project_id = self.desktop.get('/api/desktop')['projects'][0]['id']
        self.thread = self.desktop.post('/api/thread',{'project':self.project_id})['thread']

    def test_review_freezes_selected_model_and_persists_conversation(self):
        plan = self.desktop.draft({'thread':self.thread,'model':'local','prompt':'Keep the exact sum'})['draft']
        self.assertEqual(plan['write_roots'],['logic.py'])
        self.assertIn('tests',plan['inputs'])
        self.assertNotIn('.env',plan['inputs'])
        self.assertGreaterEqual(plan['context_input_tokens'],7440)
        review = self.desktop.post('/api/review',plan)
        self.assertEqual([r['profile']['id'] for r in review['eligible']],['local'])
        approval = plan|{'review':review['review']}
        with self.assertRaisesRegex(ValueError,'permissions'):
            self.desktop.post('/api/queue',approval|{'profile':'remote','location':'a100'})
        job = self.desktop.post('/api/queue',approval)['job']
        self.assertTrue((self.config.state/'runs'/job/'baseline'/'logic.py').is_file())
        self.assertFalse((self.config.state/'runs'/job/'baseline'/'.env').exists())
        reopened = Desktop(self.config,self.project,PerceptionConfig())
        self.assertEqual(reopened.get('/api/desktop')['messages'][0]['job'],job)
        followup = reopened.draft({'thread':self.thread,'model':'','prompt':'Now extend it'})['draft']
        self.assertIn('Keep the exact sum (queued)',followup['objective'])
        self.assertEqual(reopened.task(followup).attempts,2)

    def test_project_picker_requires_operator_selection_and_scopes_registered_folder(self):
        other = self.root/'other'
        other.mkdir()
        (other/'answer.js').write_text('export const answer = 42;\n')
        with patch('aiwork.desktop.choose_path',return_value=str(other)):
            selected = self.desktop.post('/api/pick',{})['project']
        thread = self.desktop.post('/api/thread',{'project':selected})['thread']
        self.assertEqual(self.desktop.workspace({'thread':thread}),other)
        with self.assertRaises(ValueError):
            self.desktop.post('/api/thread',{'project':'unregistered'})

    def test_screen_and_native_policies_remain_scoped(self):
        with self.assertRaisesRegex(ValueError,'owned laptop'):
            self.desktop.draft({'thread':self.thread,'model':'remote','prompt':'Describe','screen':{'schema':1}})
        with patch('aiwork.desktop.choose_path',return_value=''):
            self.assertEqual(self.desktop.post('/api/native',{'thread':self.thread}),{})
        self.assertEqual(self.desktop.get('/api/desktop')['native'],['binary'])


if __name__=='__main__':
    unittest.main()
