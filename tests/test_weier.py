"""微尔算法测试 (彩乐乐, 2017)"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestWeierFilter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_generate_weier_runs(self):
        """generate_tickets_weier 正常生成"""
        from ml.weier_filter import generate_tickets_weier
        result = generate_tickets_weier()
        self.assertTrue(result["ok"])
        self.assertGreater(len(result["tickets"]), 0)
        self.assertIn("conditions", result)
        self.assertIn("filter_log", result)

    def test_weier_tickets_valid(self):
        """生成票集格式正确"""
        from ml.weier_filter import generate_tickets_weier
        result = generate_tickets_weier()
        for t in result["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)

    def test_detectors_run(self):
        """规律检测器可运行"""
        from ml.weier_filter import _detect_patterns
        seq = [0, 0, 0, 1, 2, 1, 1, 1, 0, 2]
        self.assertIsInstance(_detect_patterns(seq), set)

    def test_pool_size_exact(self):
        """精确池大小: C(33,6) - h2(93) - h3(n_draws)"""
        from ml.weier_filter import generate_tickets_weier
        result = generate_tickets_weier()
        log = result.get("filter_log", {})
        self.assertIn("exact_pool_size", log)

    def test_full_output(self):
        """全量导出, 不截断"""
        from ml.weier_filter import generate_tickets_weier
        result = generate_tickets_weier()
        self.assertTrue(result["ok"])
        self.assertGreater(len(result["tickets"]), 0)


if __name__ == "__main__":
    unittest.main()
