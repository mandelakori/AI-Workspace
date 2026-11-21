"""The operator goal must remain available independently of a model-written summary."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aiwork.harness import OpenCode
from aiwork.process import Result
from aiwork.schema import Check, Profile, Task


class HarnessContextTests(unittest.TestCase):
    def test_measured_worker_source_survives_interrupted_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            work=root/'input';work.mkdir();(work/'module.py').write_text('original')
            artifacts=root/'artifacts';artifacts.mkdir()
            isolated=root/'owned-stage';isolated.mkdir()
            task=Task('public objective',work,'agent','fixture',(),(),(),mode='engineering',write_roots=('module.py',))
            profile=Profile('local','fixture','http://127.0.0.1:9999/v1')
            def interrupted(*args):
                (args[2]/'module.py').write_text('MODEL-GENERATED-CANARY')
                raise RuntimeError('fixture interruption before export')
            with (patch('aiwork.trial_budget.current',return_value={'label':'fixture-owned'}),
                  patch('aiwork.harness.mkdtemp',return_value=str(isolated)),
                  patch.object(OpenCode,'run_session',side_effect=interrupted)):
                with self.assertRaisesRegex(RuntimeError,'interruption'):
                    OpenCode('fixture').execute(profile,task,work,artifacts,'public prompt',10)
            receipt=json.loads((artifacts/'retained-stage.json').read_bytes())
            self.assertTrue(receipt['retained'])
            self.assertEqual((Path(receipt['workspace'])/'module.py').read_text(),'MODEL-GENERATED-CANARY')
            self.assertEqual((work/'module.py').read_text(),'original')

    def test_instruction_baseline_keeps_goal_and_scope_without_private_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root/"workspace"
            work.mkdir()
            artifacts = root/"artifacts"
            artifacts.mkdir()
            (root/"private.txt").write_text("PRIVATE-CANARY", encoding="utf-8")
            goal = "Implement the reviewed public feature; do not lose this objective."
            task = Task(goal, work, "agent", "test", (), ("module.py",), (Check(("{python}", "-V")),),
                        mode="engineering", write_roots=("module.py",), commands=(Check(("{python}", "-V")),))
            profile = Profile("local", "fixture", "http://127.0.0.1:9999/v1", context=8192)
            with patch("aiwork.harness.mcp_catalog",return_value={'passed':True,'tools':[]}),patch("aiwork.provider_gate.guarded_run", return_value=Result(0, 0, "", "", False, False)) as run:
                OpenCode("fixture").run_session(profile, task, work, artifacts, "Initial request", 10, artifacts/'tool.json', None)
            config = run.call_args.args[5]
            instruction = Path(config["instructions"][0])
            text = instruction.read_text()
            # Windows runner temp paths can use an 8.3 alias; compare resolved paths.
            self.assertTrue(instruction.is_relative_to(artifacts.resolve()))
            self.assertIn(goal, text)
            self.assertIn("module.py", text)
            self.assertNotIn("PRIVATE-CANARY", text)
            self.assertNotIn("compaction", config)
            self.assertIn({"action":"external_directory","resource":"*","effect":"deny"}, config["permissions"])
