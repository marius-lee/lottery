"""覆盖设计单元测试 — covering_design.py"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSimannealCovering(unittest.TestCase):
    """simanneal_covering 基础功能"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_simanneal_covering_runs(self):
        """v=15, t=4 可完成迭代"""
        from ml.covering_design import simanneal_covering
        hot_numbers = list(range(1, 16))
        tickets, cov = simanneal_covering(hot_numbers, n_tickets=6, t=4, iterations=500)
        self.assertGreater(len(tickets), 0)
        for t in tickets:
            self.assertEqual(len(t), 6)
        self.assertGreaterEqual(cov, 0)


class TestBuildCoveringTickets(unittest.TestCase):
    """build_covering_tickets 入口"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_build_covering_tickets_small(self):
        """v=12, t=4 可成功构建"""
        from ml.covering_design import build_covering_tickets
        hot = list(range(1, 13))
        result = build_covering_tickets(hot, t=4)
        self.assertTrue(result["ok"])
        self.assertEqual(result["v"], 12)
        self.assertEqual(result["k"], 6)
        self.assertGreater(result["ticket_count"], 0)

    def test_build_covering_tickets_too_few(self):
        """v < k 应返回错误"""
        from ml.covering_design import build_covering_tickets
        hot = [1, 2, 3]
        result = build_covering_tickets(hot, t=4)
        self.assertFalse(result["ok"])

    def test_candidate_set(self):
        """generate_candidate_set 取 top-v"""
        from ml.covering_design import generate_candidate_set
        probs = {i: 1.0 / i for i in range(1, 34)}
        cand = generate_candidate_set(probs, size=15)
        self.assertEqual(len(cand), 15)

    def test_lottery_ev_calculator(self):
        """EV 计算器返回有效结构"""
        from ml.covering_design import lottery_ev_calculator
        tickets = [[1, 2, 3, 4, 5, 6]]
        hot = list(range(1, 16))
        blue_probs = {str(n): 0.0625 for n in range(1, 17)}
        ev = lottery_ev_calculator(tickets, hot, blue_probs, coverage_pct=95)
        self.assertIn("est_secondary_ev_rmb", ev)
        self.assertIn("ev_cost_ratio", ev)
        self.assertIn("prob_all_6_in_hot_pct", ev)


class TestCoveringWithBlue(unittest.TestCase):
    """Tier 3: 覆盖设计 + 蓝球分配"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_generate_tickets_covering_runs(self):
        """覆盖设计 + 蓝球分配生成有效票集"""
        from ml.micro_portfolio import generate_tickets_covering
        result = generate_tickets_covering(n=6, hot_numbers=list(range(1, 16)), t=4)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 6)
        for t in result["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)
        self.assertIn("covering", result)
        self.assertIn("estimated_coverage_pct", result["covering"])

    def test_generate_tickets_covering_blue_unique(self):
        """覆盖票蓝球注间不重复"""
        from ml.micro_portfolio import generate_tickets_covering
        result = generate_tickets_covering(n=6, hot_numbers=list(range(1, 16)), t=4)
        blues = [t["blue"] for t in result["tickets"]]
        self.assertEqual(len(set(blues)), len(blues))

    def test_generate_tickets_covering_insufficient_hot(self):
        """热号不足6个时返回error"""
        from ml.micro_portfolio import generate_tickets_covering
        result = generate_tickets_covering(n=3, hot_numbers=[1, 2, 3])
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
