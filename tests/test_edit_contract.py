"""Model-independent examples: literal effects, diagnostics and semantic limits.

Only synthetic, self-authored source is used. Passing these checks establishes
the tool contract, not whether an inference model understands its description.
"""
import ast
from pathlib import Path
import tempfile
import unittest

from aiwork.mcp import focus
from aiwork.source_edit import apply_edit, EditRejected, sha


class EditContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / 'sample.py'
        self.lock = self.root / 'edit.lock'

    def edit(self, old, new, mode, fingerprint=None):
        return apply_edit(self.root, ('sample.py',), {
            'path': 'sample.py', 'expected_sha256': fingerprint or sha(self.path.read_bytes()),
            'old': old, 'new': new, 'mode': mode,
        }, self.lock)

    def test_mode_examples_distinguish_replacement_from_insertion(self):
        original = b'# prefix\n# anchor\n# suffix\n'
        examples = [
            ('replace', '# addition\n', b'# prefix\n# addition\n# suffix\n'),
            ('before', '# addition\n', b'# prefix\n# addition\n# anchor\n# suffix\n'),
            ('after', '# addition\n', b'# prefix\n# anchor\n# addition\n# suffix\n'),
            ('replace', '# anchor\n# addition\n', b'# prefix\n# anchor\n# addition\n# suffix\n'),
            ('before', '# anchor\n# addition\n', b'# prefix\n# anchor\n# addition\n# anchor\n# suffix\n'),
            ('after', '# anchor\n# addition\n', b'# prefix\n# anchor\n# anchor\n# addition\n# suffix\n'),
        ]
        for mode, payload, expected in examples:
            with self.subTest(mode=mode, payload=payload):
                self.path.write_bytes(original)
                result = self.edit('# anchor\n', payload, mode)
                self.assertTrue(result['applied'])
                self.assertEqual(self.path.read_bytes(), expected)
                self.assertEqual(result['sha256'], sha(expected))

    def test_exact_match_and_valid_python_do_not_establish_correct_behavior(self):
        original = 'def collect():\n    values = []\n    values.append("existing")\n    return values\n'
        self.path.write_text(original, encoding='utf-8', newline='\n')
        anchor = '    values.append("existing")\n'
        result = self.edit(anchor, anchor + '    values.append("addition")\n', 'after')
        self.assertTrue(result['passed'])
        # Inspect literals in our synthetic source; never execute model proposals.
        body = ast.parse(self.path.read_bytes()).body[0].body
        values = [ast.literal_eval(node.value.args[0]) for node in body if isinstance(node, ast.Expr)]
        self.assertEqual(values, ['existing', 'existing', 'addition'])
        self.assertNotEqual(values, ['existing', 'addition'])

    def test_error_hint_supports_exact_recovery_and_stale_source_still_blocks(self):
        original = b'def collect():\n    values = []\n    values.append("existing")\n    return values\n'
        self.path.write_bytes(original)
        with self.assertRaises(EditRejected) as caught:
            self.edit('    values.append("existing")\n return values\n', '', 'replace')
        error = caught.exception.diagnostic
        self.assertEqual(error['code'], 'anchor_mismatch')
        self.assertEqual(error['anchor_matches'], 0)
        self.assertTrue(error['unchanged'])
        self.assertEqual(error['actual_sha256'], sha(original))
        self.assertEqual(self.path.read_bytes(), original)
        inspected = focus(self.root, error['focus_arguments'])
        self.assertEqual(inspected['line'], 3)
        anchor = inspected['source'].splitlines(keepends=True)[0]
        self.edit(anchor, '    values.append("addition")\n', 'after', inspected['sha256'])
        self.assertEqual(self.path.read_bytes(), original.replace(
            anchor.encode(), anchor.encode() + b'    values.append("addition")\n'))
        before = self.path.read_bytes()
        with self.assertRaises(EditRejected) as caught:
            self.edit(anchor, '', 'replace', inspected['sha256'])
        self.assertEqual(caught.exception.diagnostic['code'], 'stale_source')
        self.assertTrue(caught.exception.diagnostic['unchanged'])
        self.assertEqual(self.path.read_bytes(), before)
