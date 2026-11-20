"""Public requirements only, not an HTTPX implementation or final sealed suite."""
import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path.cwd()))
import httpx
from httpx._utils import URLPattern

assert Path(httpx.__file__).resolve().is_relative_to(Path.cwd().resolve())


class PublicPathMounts(unittest.TestCase):
    def test_legacy_scheme(self):
        self.assertFalse(URLPattern("https://").matches(httpx.URL("http://service.test/api")))

    def test_legacy_wildcard(self):
        self.assertTrue(URLPattern("all://*.service.test").matches(httpx.URL("http://sub.service.test/x")))
        self.assertFalse(URLPattern("all://*.service.test").matches(httpx.URL("http://service.test/x")))

    def test_legacy_port(self):
        self.assertFalse(URLPattern("https://service.test:8443").matches(httpx.URL("https://service.test/api")))

    def test_root_and_empty_paths_remain_unrestricted(self):
        for pattern in ["https://service.test", "https://service.test/"]:
            self.assertTrue(URLPattern(pattern).matches(httpx.URL("https://service.test/anything")))

    def test_invalid_legacy_pattern(self):
        with self.assertRaises(ValueError): URLPattern("https")

    def test_exact_and_descendant(self):
        pattern = URLPattern("https://service.test/api")
        self.assertTrue(pattern.matches(httpx.URL("https://service.test/api")))
        self.assertTrue(pattern.matches(httpx.URL("https://service.test/api/books")))

    def test_segment_boundary(self):
        self.assertFalse(URLPattern("https://service.test/api").matches(httpx.URL("https://service.test/apix")))

    def test_unrelated_path(self):
        self.assertFalse(URLPattern("https://service.test/api").matches(httpx.URL("https://service.test/status")))

    def test_case_sensitive(self):
        self.assertFalse(URLPattern("https://service.test/API").matches(httpx.URL("https://service.test/api")))

    def test_trailing_slash_equivalence(self):
        for suffix in ["", "/", "/books"]:
            self.assertTrue(URLPattern("https://service.test/api/").matches(httpx.URL("https://service.test/api"+suffix)))
        self.assertFalse(URLPattern("https://service.test/api/").matches(httpx.URL("https://service.test/apix")))

    def test_queries_and_fragments_do_not_change_scope(self):
        pattern=URLPattern("https://service.test/api?q=one#section")
        self.assertTrue(pattern.matches(httpx.URL("https://service.test/api?q=two")))
        self.assertFalse(pattern.matches(httpx.URL("https://service.test/other?q=one")))

    def test_encoded_slash_is_not_a_separator(self):
        self.assertFalse(URLPattern("https://service.test/api").matches(httpx.URL("https://service.test/api%2Fbooks")))

    def test_path_priority(self):
        values=[URLPattern("https://service.test/"),URLPattern("https://service.test/api"),URLPattern("https://service.test/api/v2")]
        self.assertEqual([value.pattern for value in sorted(values)],list(reversed([value.pattern for value in values])))

    def test_legacy_priority_precedes_path_length(self):
        values=[URLPattern("all://service.test/api/v2"),URLPattern("https://service.test/api")]
        self.assertEqual(sorted(values)[0].pattern,"https://service.test/api")

    def test_sync_mount_integration(self):
        def transport(label): return httpx.MockTransport(lambda request:httpx.Response(200,text=label))
        mounts={"https://service.test/api":transport("api"),"https://service.test/api/v2":transport("v2")}
        with httpx.Client(transport=transport("default"),mounts=mounts,trust_env=False) as client:
            for path,label in [("/api","api"),("/api/v2/books","v2"),("/status","default"),("/apix","default")]:
                self.assertEqual(client.get("https://service.test"+path).text,label)

    def test_async_mount_integration(self):
        async def check():
            def transport(label): return httpx.MockTransport(lambda request:httpx.Response(200,text=label))
            async with httpx.AsyncClient(transport=transport("default"),mounts={"https://service.test/api":transport("api")},trust_env=False) as client:
                self.assertEqual((await client.get("https://service.test/status")).text,"default")
                self.assertEqual((await client.get("https://service.test/api/books")).text,"api")
        asyncio.run(check())


if __name__ == "__main__":
    unittest.main(verbosity=2)
