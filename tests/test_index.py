import unittest

from aiwork.index import python_metadata


class IndexTests(unittest.TestCase):
    def test_all_import_names_and_relative_imports_are_indexed(self):
        source = b"import json as j, pathlib\nfrom .models import Entry\nfrom . import parse, render\ndef work(): pass\n"
        symbols, imports = python_metadata(source, "sample.py")
        self.assertEqual(symbols, ["work"])
        self.assertEqual(imports, ["json", "pathlib", ".models", ".parse", ".render"])

    def test_invalid_source_is_an_empty_result(self):
        self.assertEqual(python_metadata(b"def (", "broken.py"), ([], []))
