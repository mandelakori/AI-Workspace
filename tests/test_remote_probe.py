from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from aiwork.schema import Profile
from examples.phase4 import remote_probe


class RemoteProbeTests(TestCase):
    def test_failed_request_is_recorded_without_exceeding_the_twelve_request_budget(self):
        profile = Profile("a100", "fake", "http://127.0.0.1:18882/v1",
                          engine="llamacpp", location="a100", reasoning_effort="none")
        controller = Mock()
        controller.planes = {"a100": Mock()}
        controller.planes["a100"].reserve.return_value = nullcontext()
        posts = []

        def respond(url, method="GET", body=None, **kwargs):
            if method == "GET":
                return {"total_slots": 1, "default_generation_settings": {"n_ctx": 8192}}
            posts.append(body)
            if len(posts) == 1:
                raise TimeoutError("test timeout")
            first = 33 if "33 to 64" in body["messages"][0]["content"] else 1
            return {"choices": [{"message": {"content": " ".join(map(str, range(first, first + 32)))}}],
                    "usage": {"completion_tokens": 64}}

        with TemporaryDirectory() as directory:
            root = Path(directory)
            controller.config.state = root
            with (patch.object(remote_probe, "a100_session", return_value=nullcontext()),
                  patch.object(remote_probe, "request", side_effect=respond)):
                report = remote_probe.throughput(controller, profile, root)
            self.assertEqual(len(list(root.glob("batch-*.json"))), 6)
        self.assertEqual(len(posts), 12)
        self.assertTrue(all(body["chat_template_kwargs"] == {"enable_thinking": False} for body in posts))
        self.assertEqual((report["reported_slots"], report["correct"], report["status"]), (1, 11, "failed"))
