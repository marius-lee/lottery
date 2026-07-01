"""集成测试 — HTTP API 端点"""
import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, PORT = "127.0.0.1", 18520


class TestServer(unittest.TestCase):

    server = None

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)
        from http.server import HTTPServer
        from server.handler import Handler
        from server import db
        db.init_db()
        cls.server = HTTPServer((HOST, PORT), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()

    def _get(self, path, timeout=5):
        url = f"http://{HOST}:{PORT}{path}"
        for _ in range(3):
            try:
                resp = urllib.request.urlopen(url, timeout=timeout)
                body = resp.read().decode("utf-8")
                return json.loads(body) if body.strip() else None
            except (urllib.error.URLError, ConnectionResetError, ConnectionAbortedError):
                time.sleep(0.5)
        self.fail(f"GET {url} 失败")

    def test_root(self):
        resp = urllib.request.urlopen(f"http://{HOST}:{PORT}/", timeout=5)
        html = resp.read().decode("utf-8")
        self.assertIn("双色球", html)

    def test_api_data(self):
        d = self._get("/api/data")
        self.assertTrue(d["ok"])
        self.assertGreater(d["count"], 0)

    def test_api_micro_tickets(self):
        d = self._get("/api/micro/tickets?n=3")
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["tickets"]), 3)
        for t in d["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertIsInstance(t["blue"], int)
        self.assertEqual(d["cost_rmb"], 6)

    def test_api_micro_3tickets(self):
        d = self._get("/api/micro/3tickets")
        self.assertTrue(d["ok"])

    def test_api_rules(self):
        d = self._get("/api/rules/status")
        self.assertIn("h2_arithmetic", d)

    def test_api_recent_bias(self):
        d = self._get("/api/recent-bias")
        self.assertTrue(d["ok"])
        self.assertIn("hot_reds", d)

    def test_api_user_picks(self):
        d = self._get("/api/user-picks")
        self.assertTrue(d["ok"])

    def test_api_stats(self):
        d = self._get("/api/stats", timeout=15)
        self.assertTrue(d["ok"])

    def test_api_compare(self):
        d = self._get("/api/compare")
        self.assertTrue(d["ok"])


if __name__ == "__main__":
    unittest.main()
