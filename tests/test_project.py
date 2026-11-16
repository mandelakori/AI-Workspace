import os
import tempfile
import unittest
from pathlib import Path

from aiwork.project import ProjectStore


class ProjectIndexTests(unittest.TestCase):
    def test_refresh_finds_same_size_same_timestamp_change(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "src"
            root.mkdir()
            source = root / "invoice.py"
            dependency = root / "taxes.py"
            source.write_text("import taxes\ndef invoice(): pass\n", encoding="utf-8")
            dependency.write_text("rate = 1\n", encoding="utf-8")
            store = ProjectStore(base / "state")
            self.assertEqual(store.refresh(root)["new_metadata"], 2)
            focus = store.focus(root, "invoice", 2)
            self.assertEqual(focus["inputs"], ["invoice.py", "taxes.py"])
            self.assertEqual(focus["matches"][0]["depends_on"], ["taxes.py"])
            store.record("attempt", root, "verified", base / "logs",
                         {row["path"]: row["sha256"] for row in focus["matches"]})
            self.assertTrue(store.recall(root)[0]["matches_index"])
            self.assertEqual(store.refresh(root)["new_metadata"], 0)
            stamp = dependency.stat()
            dependency.write_text("rate = 2\n", encoding="utf-8")
            os.utime(dependency, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self.assertEqual(store.refresh(root)["updated"], 1)
            self.assertFalse(store.recall(root)[0]["matches_index"])
            dependency.unlink()
            self.assertEqual(store.refresh(root)["removed"], 1)
            self.assertEqual(store.focus(root, "invoice", 2)["inputs"], ["invoice.py"])

    def test_focus_beyond_workspace_staging_limit(self):
        from aiwork.workspace import FILE_LIMIT

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repository"
            root.mkdir()
            for index in range(FILE_LIMIT):
                (root / f"file-{index:05}.txt").touch()
            (root / "billing.py").write_text("def pricing(): pass\n", encoding="utf-8")
            store = ProjectStore(base / "state")
            self.assertEqual(store.refresh(root)["files"], FILE_LIMIT + 1)
            self.assertEqual(store.focus(root, "pricing", 1)["inputs"], ["billing.py"])
