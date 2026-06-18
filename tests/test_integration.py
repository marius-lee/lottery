"""集成测试 — 启动服务器并验证 API 端点

用法:
  python3 -m pytest tests/test_integration.py -v --tb=short -k 'not covering'
"""
import unittest
import json
import sys
import os
import threading
import urllib.request
import urllib.error
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, PORT = "127.0.0.1", 18520


class TestServerAPI(unittest.TestCase):
    """启动测试服务器并验证 API 端点"""

    server = None
    server_thread = None

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)
        from http.server import HTTPServer
        from server.handler import Handler
        from server import db
        db.init_db()
        cls.server = HTTPServer((HOST, PORT), Handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
        time.sleep(0.3)

    def _get(self, path, timeout=5):
        url = f"http://{HOST}:{PORT}{path}"
        for attempt in range(3):
            try:
                resp = urllib.request.urlopen(url, timeout=timeout)
                body = resp.read().decode("utf-8")
                return json.loads(body) if body.strip() else None
            except (urllib.error.URLError, ConnectionResetError, ConnectionAbortedError):
                time.sleep(0.5)
        self.fail(f"GET {url} 失败 (重试3次, timeout={timeout}s)")

    # ========== 快速端点 (前 7 个) ==========

    def test_01_root_html(self):
        """GET / → 返回 HTML"""
        resp = urllib.request.urlopen(f"http://{HOST}:{PORT}/", timeout=5)
        html = resp.read().decode("utf-8")
        self.assertIn("html", html.lower())
        self.assertIn("双色球", html)

    def test_02_api_data(self):
        """GET /api/data → ok=True + 开奖期数 > 0"""
        d = self._get("/api/data")
        self.assertTrue(d["ok"])
        self.assertGreater(d["count"], 0)

    def test_03_api_micro_tickets(self):
        """GET /api/micro/tickets?n=3 → 3 注"""
        d = self._get("/api/micro/tickets?n=3")
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["tickets"]), 3)
        for t in d["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertIsInstance(t["blue"], int)

    def test_04_api_micro_tickets_10(self):
        """GET /api/micro/tickets?n=10 → cost=20"""
        d = self._get("/api/micro/tickets?n=10")
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["tickets"]), 10)
        self.assertEqual(d["cost_rmb"], 20)

    def test_05_api_micro_tickets_soft(self):
        """GET /api/micro/tickets?n=3&soft=1"""
        d = self._get("/api/micro/tickets?n=3&soft=1")
        self.assertTrue(d["ok"])
        self.assertTrue(d["soft_filter"])

    def test_06_api_micro_3tickets(self):
        """GET /api/micro/3tickets"""
        d = self._get("/api/micro/3tickets")
        self.assertTrue(d["ok"])

    def test_07_api_rules_status(self):
        """GET /api/rules/status"""
        d = self._get("/api/rules/status")
        self.assertIn("h2_arithmetic", d)
        self.assertIn("h3_historical", d)

    # ========== 慢端点 (单独使用长 timeout) ==========

    def test_08_api_covering_generate(self):
        """GET /api/covering/generate?v=8&t=4 — 小规模覆盖 (快速)"""
        d = self._get("/api/covering/generate?v=8&t=4", timeout=30)
        self.assertTrue(d["ok"])

    def test_09_api_evaluate_prizes(self):
        """GET /api/evaluate/prizes?n=3"""
        d = self._get("/api/evaluate/prizes?n=3")
        self.assertTrue(d["ok"])

    def test_10_api_recommend(self):
        """GET /api/recommend"""
        d = self._get("/api/recommend", timeout=15)
        self.assertTrue(d["ok"])

    def test_11_api_compare_ready(self):
        """GET /api/compare/ready"""
        d = self._get("/api/compare/ready")
        self.assertTrue(d["ok"])

    def test_12_api_flush_cache(self):
        """GET /api/flush-cache"""
        d = self._get("/api/flush-cache")
        self.assertTrue(d["ok"])

    def test_13_api_stats(self):
        """GET /api/stats"""
        d = self._get("/api/stats", timeout=15)
        self.assertTrue(d["ok"])

    def test_14_api_data_count(self):
        """/api/data count <= total"""
        d = self._get("/api/data")
        self.assertGreaterEqual(d["total"], d["count"])


    def test_15_api_covering_diverse(self):
        """GET /api/covering-diverse?v=10&t=4&n=4"""
        d = self._get("/api/covering-diverse?v=10&t=4&n=4", timeout=30)
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["tickets"]), 4)
        self.assertIn("covering", d)
        for t in d["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)


if __name__ == "__main__":
    unittest.main()
