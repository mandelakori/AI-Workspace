"""Opt-in integration check using installed OpenCode and an inert local provider."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4

from aiwork.harness import OpenCode, opencode_path
from aiwork.schema import Check, Profile, Task


@unittest.skipUnless(os.environ.get("AIWORK_TEST_OPENCODE_BOUNDARY"), "requires installed OpenCode and loopback")
class OpenCodeBoundaryTests(unittest.TestCase):
    def test_external_files_are_denied_and_staged_edits_survive(self):
        binary = opencode_path()
        if not binary or not shutil.which("git"):
            self.skipTest("requires OpenCode and Git")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", "--template=", str(root)], check=True)
            work = root / "workspace"
            work.mkdir()
            artifacts = root / "artifacts"
            artifacts.mkdir()
            private_marker, working_marker = f"private-{uuid4().hex}", f"inside-{uuid4().hex}"
            outside = root / ("canary-" + uuid4().hex + ".txt")
            outside.write_text(private_marker, encoding="utf-8")
            (work / "allowed.txt").write_text(working_marker, encoding="utf-8")
            actions = [
                ("read", {"path": "allowed.txt"}),
                ("read", {"path": str(outside)}),
                ("glob", {"path": str(outside.parent), "pattern": outside.name}),
                ("grep", {"path": str(outside.parent), "pattern": private_marker}),
                ("write", {"path": "result.txt", "content": "isolated edit\n"}),
            ]
            tool_results = []
            offered = set()

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def do_GET(self):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"object":"list","data":[{"id":"boundary-fixture","object":"model"}]}')

                def do_POST(self):
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    offered.update(item["function"]["name"] for item in request.get("tools", []))
                    messages = [msg for msg in request["messages"] if msg["role"] == "tool"]
                    calls = []
                    if request.get("tools") and not messages:
                        calls = [{"index": index, "id": f"check_{index}", "type": "function",
                                  "function": {"name": name, "arguments": json.dumps(args)}}
                                 for index, (name, args) in enumerate(actions) if name in offered]
                    tool_results.extend(messages)
                    delta = {"role": "assistant", "tool_calls": calls} if calls else {
                        "role": "assistant", "content": "Boundary check completed."}
                    chunks = [(delta, None), ({}, "tool_calls" if calls else "stop")]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for payload, reason in chunks:
                        data = {"id": "scope-test", "object": "chat.completion.chunk",
                                "created": 1, "model": "boundary-fixture",
                                "choices": [{"index": 0, "delta": payload, "finish_reason": reason}]}
                        self.wfile.write(("data: " + json.dumps(data) + "\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")

            with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    profile = Profile("boundary", "boundary-fixture",
                                      f"http://127.0.0.1:{server.server_port}/v1")
                    task = Task("Check staged access", work, "agent", "test", (), ("result.txt",),
                                (Check(("{python}", "--version")),))
                    result = OpenCode(binary).execute(profile, task, work, artifacts, "Check task scope.", 30)
                finally:
                    server.shutdown()
                    thread.join()
            self.assertFalse(result.timed_out, result.stderr)
            self.assertTrue({"read", "glob", "grep", "write"} <= offered)
            replies = {message["tool_call_id"]: json.dumps(message["content"]) for message in tool_results}
            self.assertIn(working_marker, replies["check_0"])
            self.assertNotIn(private_marker, replies["check_1"])
            self.assertRegex(replies["check_2"], r"(?i)blocked|denied|outside|permission")
            self.assertRegex(replies["check_3"], r"(?i)blocked|denied|outside|permission")
            self.assertRegex(replies["check_1"], r"(?i)blocked|denied|outside|permission")
            self.assertEqual(outside.read_text(encoding="utf-8"), private_marker)
            self.assertEqual((work / "result.txt").read_text(encoding="utf-8"), "isolated edit\n")
