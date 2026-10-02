import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nichu.server import handler_for
from tests import test_dictionary as fixtures


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.DictionaryTests.setUpClass()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(fixtures.DictionaryTests.dictionary))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()
        fixtures.DictionaryTests.tearDownClass()

    def get(self, path):
        return urlopen(self.base + path, timeout=5)

    def test_api_roundtrip_and_source_script(self):
        with self.get("/api/search?" + urlencode({"q": "学校", "mode": "exact"})) as response:
            body = json.load(response)
        identifier = body["results"][0]["id"]
        with self.get(f"/api/entry/{identifier}?script=original") as response:
            raw = json.load(response)
        self.assertIn("學習", raw["senses"][0]["glosses"][0])
        with self.get(f"/api/entry/{identifier}") as response:
            simplified = json.load(response)
        self.assertIn("学习", simplified["senses"][0]["glosses"][0])

    def test_assets_with_content_security_policy(self):
        for path in ["/", "/guide", "/app.js", "/style.css", "/icon.svg"]:
            with self.get(path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("connect-src 'self'", response.headers["Content-Security-Policy"])
                self.assertTrue(response.read())

    def test_errors_are_json(self):
        for path, code in [("/api/search?limit=no", 400), ("/api/search?mode=bad", 400), ("/api/entry/missing", 404), ("/data/dictionary.sqlite3", 404), ("/../LICENSE", 404)]:
            with self.assertRaises(HTTPError) as result:
                self.get(path)
            self.assertEqual(result.exception.code, code)
            self.assertIn("error", json.loads(result.exception.read()))
            result.exception.close()

    def test_dns_rebinding_host_rejected(self):
        request = Request(self.base + "/api/stats", headers={"Host": "untrusted.example"})
        with self.assertRaises(HTTPError) as result:
            urlopen(request, timeout=5)
        self.assertEqual(result.exception.code, 403)
        result.exception.close()


if __name__ == "__main__":
    unittest.main()
