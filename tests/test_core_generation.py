"""微投资组合单元测试 — micro_portfolio.py"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestGenerateTickets(unittest.TestCase):
    """验证 generate_tickets 输出结构和边界条件"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_generate_3_tickets_default(self):
        """默认 n=3, soft=False 生成非空票集"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, soft=False)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)
        for t in result["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)
        self.assertIn("algorithm", result)
        self.assertIn("cost_rmb", result)

    def test_generate_1_ticket(self):
        """n=1 生成单注"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=1)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 1)

    def test_generate_10_tickets(self):
        """n=10 生成十注 (测试大量采样不重复)"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=10)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 10)
        # 检查无重复组合
        combos = {tuple(t["reds"] + [t["blue"]]) for t in result["tickets"]}
        self.assertEqual(len(combos), 10, "10 注不应有重复")

    def test_generate_tickets_with_soft(self):
        """启用软过滤不应影响基本输出"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, soft=True)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)

    def test_red_ball_range(self):
        """红球 1-33, 蓝球 1-16"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=5)
        for t in result["tickets"]:
            for r in t["reds"]:
                self.assertGreaterEqual(r, 1)
                self.assertLessEqual(r, 33)
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)

    def test_cost_calculation(self):
        """成本 = n × 2 元"""
        from ml.micro_portfolio import generate_tickets
        for n in [1, 3, 5]:
            result = generate_tickets(n=n)
            self.assertEqual(result["cost_rmb"], n * 2)

    def test_soft_excluded_count(self):
        """soft_excluded 应有数值"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3)
        self.assertIn("soft_excluded", result)


class TestBlueWeights(unittest.TestCase):
    """蓝球频率权重函数"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_blue_freq_weights_sum_to_1(self):
        """蓝球概率和为 1.0"""
        from ml.micro_portfolio import _blue_freq_weights
        weights = _blue_freq_weights()
        self.assertAlmostEqual(sum(weights), 1.0, places=6)
        self.assertEqual(len(weights), 16)

    def test_blue_freq_weights_positive(self):
        """所有蓝球概率 > 0 (Laplace 平滑保证)"""
        from ml.micro_portfolio import _blue_freq_weights
        weights = _blue_freq_weights()
        for w in weights:
            self.assertGreater(w, 0)

    def test_weighted_blue_choice(self):
        """_weighted_choice 蓝球选择返回值范围"""
        from ml.micro_portfolio import _weighted_choice, _blue_freq_weights
        weights = _blue_freq_weights()
        candidates = list(range(1, 17))
        for _ in range(50):
            b = _weighted_choice(weights, candidates)
            self.assertIsNotNone(b)
            self.assertGreaterEqual(b, 1)
            self.assertLessEqual(b, 16)


class TestFallback(unittest.TestCase):
    """故障降级路径"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_fallback_output(self):
        """_generate_fallback_tickets 结构与 normal 相同"""
        from ml.micro_portfolio import _generate_fallback_tickets
        result = _generate_fallback_tickets(n=3)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)
        self.assertEqual(result["algorithm"], "Fallback-Random")
        for t in result["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)


class TestMaxOverlap(unittest.TestCase):
    """Tier 1: 注间分散约束 max_overlap"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_max_overlap_zero_disjoint(self):
        """max_overlap=0: 所有注对无共享红球"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, max_overlap=0)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)
        for i in range(len(result["tickets"])):
            for j in range(i + 1, len(result["tickets"])):
                overlap = len(set(result["tickets"][i]["reds"])
                              & set(result["tickets"][j]["reds"]))
                self.assertEqual(overlap, 0,
                    f"票{i},{j}共享{overlap}个红球, max_overlap=0要求0")

    def test_max_overlap_two(self):
        """max_overlap=2: 注对共享≤2红球"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, max_overlap=2)
        self.assertTrue(result["ok"])
        for i in range(len(result["tickets"])):
            for j in range(i + 1, len(result["tickets"])):
                overlap = len(set(result["tickets"][i]["reds"])
                              & set(result["tickets"][j]["reds"]))
                self.assertLessEqual(overlap, 2)

    def test_max_overlap_default_none_backward_compat(self):
        """max_overlap=None: 与不加约束行为一致(向后兼容)"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, max_overlap=None)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)
        for t in result["tickets"]:
            self.assertEqual(len(t["reds"]), 6)

    def test_max_overlap_extreme_no_crash(self):
        """n=10, max_overlap=0: 极端的束不崩溃"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=10, max_overlap=0)
        self.assertTrue(result["ok"])
        self.assertGreater(len(result["tickets"]), 0)


class TestGreedyDiversity(unittest.TestCase):
    """Tier 2: 贪心多样性选注"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_greedy_runs(self):
        """diversity_mode='greedy' 生成正确数量票数"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, diversity_mode='greedy')
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)
        self.assertIn("Greedy", result["algorithm"])

    def test_greedy_vs_random_diversity(self):
        """贪心min Jaccard距离 ≥ 随机采样"""
        from ml.micro_portfolio import generate_tickets, _jaccard_distance

        def min_jaccard(ticks):
            dists = []
            for i in range(len(ticks)):
                for j in range(i + 1, len(ticks)):
                    dists.append(_jaccard_distance(
                        tuple(ticks[i]["reds"]), tuple(ticks[j]["reds"])))
            return min(dists) if dists else 0.0

        result_g = generate_tickets(n=5, diversity_mode='greedy')
        result_r = generate_tickets(n=5)
        self.assertGreaterEqual(min_jaccard(result_g["tickets"]),
                                min_jaccard(result_r["tickets"]))


class TestFivePeriod(unittest.TestCase):
    """五期断蓝法 (刘大军, 2011)"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_five_period_boost_returns_16(self):
        """_five_period_boost 返回16个元素"""
        from ml.micro_portfolio import _five_period_boost
        boost = _five_period_boost()
        self.assertEqual(len(boost), 16)

    def test_five_period_boost_values(self):
        """五期均值±4范围内=1.0, 范围外≈0(排除)"""
        from ml.micro_portfolio import _five_period_boost
        boost = _five_period_boost()
        self.assertIn(1.0, boost)    # 范围内保留
        self.assertIn(0.01, boost)   # 范围外排除

    def test_five_period_off_by_default(self):
        """five_period=False: 行为不变(向后兼容)"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, five_period=False)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)

    def test_five_period_on_runs(self):
        """five_period=True: 正常生成"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, five_period=True)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)
        for t in result["tickets"]:
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)


class TestPatternRules(unittest.TestCase):
    """图形规律 (刘大军 Ch3-4, 2011)"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_pattern_boost_returns_16(self):
        """_pattern_blue_boost 返回16个元素"""
        from ml.micro_portfolio import _pattern_blue_boost
        boost = _pattern_blue_boost()
        self.assertEqual(len(boost), 16)

    def test_pattern_runs(self):
        """pattern_rules=True 正常生成"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, pattern_rules=True)
        self.assertTrue(result["ok"])
        for t in result["tickets"]:
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)

    def test_pattern_off_by_default(self):
        """pattern_rules=False: 向后兼容"""
        from ml.micro_portfolio import generate_tickets
        result = generate_tickets(n=3, pattern_rules=False)
        self.assertTrue(result["ok"])


class TestBuildPool(unittest.TestCase):
    """_build_pool 和 rule_status"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_build_pool_runs(self):
        """_build_pool 可成功执行 (需要数据库有数据)"""
        from ml.micro_portfolio import _build_pool, rule_status
        from server.db import load_draws
        data = load_draws()
        if len(data) >= 10:
            _build_pool()
            status = rule_status()
            self.assertIn("h2_arithmetic", status)
            self.assertIn("h3_historical", status)
            self.assertIn("s1_consecutive", status)
            self.assertIn("s4_max_gap", status)


if __name__ == "__main__":
    unittest.main()
