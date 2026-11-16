from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from aiwork.cloud import Lambda, Lifecycle
from aiwork.http import HTTPFailure


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.provider = Mock()
        self.provider.instances.return_value = []
        self.provider.types.return_value = {"gpu_a100": {"regions_with_capacity_available": [{"name": "zone"}]}}
        self.provider.launch.return_value = "test-id"
        self.row = {"id": "test-id", "name": "aiwork-test", "status": "active", "ip": "198.51.100.1"}
        self.provider.instance.return_value = self.row
        self.cfg = {"name": "aiwork-test", "region": "zone",
                    "instance_type": "gpu_a100", "ssh_key_name": "registered-test"}
        self.lifecycle = Lifecycle(self.provider, self.cfg, self.root)

    def test_opt_in_and_ready(self):
        with self.assertRaisesRegex(RuntimeError, "launch disabled"):
            self.lifecycle.acquire(2, allow_launch=True)
        self.provider.launch.assert_not_called()
        self.cfg["allow_launch"] = True
        self.assertEqual(self.lifecycle.acquire(2, allow_launch=True), self.row)
        self.provider.launch.assert_called_once_with({
            "name": "aiwork-test", "instance_type_name": "gpu_a100", "region_name": "zone",
            "ssh_key_names": ["registered-test"],
        })
        self.assertFalse(self.lifecycle.intent.exists())

    def test_read_only_reuse(self):
        self.provider.instances.return_value = [self.row]
        self.assertEqual(self.lifecycle.acquire(2, allow_launch=False), self.row)
        self.provider.launch.assert_not_called()

    def test_no_capacity(self):
        self.cfg["allow_launch"] = True
        self.provider.types.return_value = {}
        with self.assertRaisesRegex(RuntimeError, "no capacity"):
            self.lifecycle.acquire(2, allow_launch=True)
        self.provider.launch.assert_not_called()

    def test_ambiguous_launch_does_not_retry(self):
        self.cfg["allow_launch"] = True
        self.provider.launch.side_effect = OSError("response lost")
        with self.assertRaises(OSError):
            self.lifecycle.acquire(2, allow_launch=True)
        with self.assertRaisesRegex(RuntimeError, "unresolved launch intent"):
            self.lifecycle.acquire(2, allow_launch=True)
        self.provider.launch.assert_called_once()

    def test_dry_run_and_termination_policy(self):
        self.provider.instances.return_value = [self.row]
        self.assertFalse(self.lifecycle.terminate("test-id", apply=False)["submitted"])
        with self.assertRaises(ValueError):
            self.lifecycle.terminate("test-id", apply=True)
        self.cfg["allow_terminate"] = True
        with self.assertRaises(ValueError):
            self.lifecycle.terminate("wrong-id", apply=True)
        self.assertTrue(self.lifecycle.terminate("test-id", apply=True)["submitted"])
        self.provider.terminate.assert_called_once_with("test-id")

    @patch.dict("os.environ", {"AIWORK_TEST_KEY": "mock-key"})
    @patch("aiwork.cloud.sleep")
    @patch("aiwork.cloud.request")
    def test_get_retries_and_drops_sensitive_fields(self, request, _):
        request.side_effect = [HTTPFailure(429), {"data": [{**self.row, "jupyter_token": "secret"}]}]
        self.assertEqual(Lambda("AIWORK_TEST_KEY").instances(), [self.row])
        self.assertEqual(request.call_count, 2)

    @patch.dict("os.environ", {"AIWORK_TEST_KEY": "mock-key"})
    @patch("aiwork.cloud.request")
    def test_post_transport_failure_never_replayed(self, request):
        request.side_effect = HTTPFailure(503)
        with self.assertRaises(HTTPFailure):
            Lambda("AIWORK_TEST_KEY").launch({"name": "aiwork-test"})
        request.assert_called_once()
