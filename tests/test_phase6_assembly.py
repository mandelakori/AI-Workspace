"""The experiment integrator must preserve code outside the assigned class."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


path = Path(__file__).resolve().parents[1] / "examples/phase6/repair_source.py"
spec = importlib.util.spec_from_file_location("phase6_repair_source", path)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class Phase6AssemblyTests(unittest.TestCase):
    def test_class_assembly_preserves_unrelated_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            target = work / "src/click/types.py"
            target.parent.mkdir(parents=True)
            original = 'BEFORE = 1\n\nclass ISODateTime:\n    old = True\n\nAFTER = 2\n'
            target.write_text(original)
            replacement = 'class ISODateTime:\n    proposed = True\n'
            repair.assemble("api", replacement, work)
            self.assertEqual(target.read_text(), original.replace('class ISODateTime:\n    old = True\n', replacement))

    def test_extra_global_scope_is_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            target = work / "src/click/types.py"
            target.parent.mkdir(parents=True)
            original = 'class ISODateTime:\n    pass\n'
            target.write_text(original)
            with self.assertRaisesRegex(ValueError, "only ISODateTime"):
                repair.assemble("api", 'import os\nclass ISODateTime:\n    pass\n', work)
            self.assertEqual(target.read_text(), original)

    def test_method_replacement_rejects_signature_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            target = work / "src/click/types.py"
            target.parent.mkdir(parents=True)
            original = 'class ISODateTime:\n    def _handle_datetime(self, value, param, ctx):\n        return value\n'
            target.write_text(original)
            with self.assertRaisesRegex(ValueError, "calling signature"):
                repair.assemble("api-method", 'def _handle_datetime(self, value):\n    return value\n', work)
            self.assertEqual(target.read_text(), original)
