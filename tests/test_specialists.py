import json
import sys
import tempfile
import unittest
from pathlib import Path

from aiwork.controller import Controller
from aiwork.schema import Config
from aiwork.specialists import capabilities


class SpecialistTests(unittest.TestCase):
    def test_named_static_adapter_is_operator_scoped_and_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "toy.elf").write_bytes(bytes([127, 69, 76, 70, 2, 1]) + bytes(14))
            manifest = root / "task.toml"
            manifest.write_text("""
objective = "Inspect the synthetic ELF header"
workspace = "project"
kind = "direct"
category = "static-adapter"
specialist = "header-review"
[[checks]]
argv = ["{python}", "-c", "print('complete')"]
""", encoding="utf-8")
            settings = {"header-review": {"artifact_formats": ["ELF"], "timeout": 5, "format": "json",
                        "argv": [sys.executable, "-c",
                                 "import json,sys; print(json.dumps({'input': sys.argv[1].split('toy.elf')[-1]}))",
                                 "{binary}"]}}
            cfg = Config(root / "state", specialists=settings)
            self.assertEqual(capabilities(cfg)[1]["formats"], ["ELF"])
            controller = Controller(cfg)
            with self.assertRaises(ValueError):
                controller.submit(manifest, False)
            result = controller.run_submitted(controller.submit(manifest, True))
            self.assertEqual(result["status"], "verified", result)
            stage = Path(result["artifacts"]) / "attempt-001"
            analysis = json.loads((stage / "analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(analysis["findings"], {"input": ""})
            self.assertTrue((stage / "specialist-process.json").is_file())
