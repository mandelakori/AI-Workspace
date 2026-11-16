import json
import tempfile
import unittest
from pathlib import Path

from aiwork.metrics import summarize_trace


class TraceTests(unittest.TestCase):
    def test_incomplete_assistant_event_preserves_later_tool_evidence(self):
        rows = [
            {"type": "assistant", "message": {"usage": {"input_tokens": 17}, "content": None}},
            {"type": "tool_use", "tool": "read"},
            {"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True}]}},
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = summarize_trace("\n".join(map(json.dumps, rows)), Path(folder))
        self.assertEqual(result["tool_calls"], {"read": 1})
        self.assertEqual(result["tool_errors"], 1)
        self.assertEqual(result["peak_reported_input_tokens"], 17)
