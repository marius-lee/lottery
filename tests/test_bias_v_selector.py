"""偏差驱动的动态v选择器测试 — bias_v_selector.py"""
import unittest
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestBiasVSelector(unittest.TestCase):
    """验证 determine_optimal_v 在不同数据量下的行为"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def setUp(self):
        from server.db import load_draws
        self.data = load_draws()

    def test_auto_v_returns_valid_range(self):
        """auto_v 返回 v 在 8-33 范围内"""
        from ml.bias_v_selector import auto_v
        result = auto_v()
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.v, 8)
        self.assertLessEqual(result.v, 33)

    def test_signal_level_is_valid(self):
        """signal_level 是合法值"""
        from ml.bias_v_selector import auto_v
        result = auto_v()
        self.assertIn(result.signal_level, ["strong", "moderate", "weak", "none"])

    def test_top_numbers_count_matches_v(self):
        """推荐的热号数量等于 v"""
        from ml.bias_v_selector import auto_v
        result = auto_v()
        self.assertEqual(len(result.top_numbers), result.v)

    def test_top_numbers_in_range(self):
        """所有热号在 1-33 范围内"""
        from ml.bias_v_selector import auto_v
        result = auto_v()
        for n in result.top_numbers:
            self.assertGreaterEqual(n, 1)
            self.assertLessEqual(n, 33)

    def test_no_duplicates_in_top_numbers(self):
        """热号列表无重复"""
        from ml.bias_v_selector import auto_v
        result = auto_v()
        self.assertEqual(len(result.top_numbers), len(set(result.top_numbers)))

    def test_reasoning_is_not_empty(self):
        """reasoning 字段有内容"""
        from ml.bias_v_selector import auto_v
        result = auto_v()
        self.assertIsNotNone(result.reasoning)
        self.assertGreater(len(result.reasoning), 10)

    def test_deviation_scores_is_dict(self):
        """deviation_scores 是 33 个号码的字典"""
        from ml.bias_v_selector import auto_v
        result = auto_v()
        self.assertEqual(len(result.deviation_scores), 33)
        for n in range(1, 34):
            self.assertIn(n, result.deviation_scores)

    def test_insufficient_data_fallback(self):
        """数据不足 100 期时回退 v=15"""
        from ml.bias_v_selector import determine_optimal_v
        fake_data = [["2026001", 1, 2, 3, 4, 5, 6, 1]] * 50
        result = determine_optimal_v(fake_data)
        self.assertEqual(result.v, 15)
        self.assertEqual(result.signal_level, "none")

    def test_signal_discount_bounds(self):
        """_signal_discount 在 [0, 1] 范围内"""
        from ml.bias_v_selector import _signal_discount
        for level in ["strong", "moderate", "weak", "none"]:
            for rank in range(1, 34):
                d = _signal_discount(rank, 15, level)
                self.assertGreaterEqual(d, 0.0)
                self.assertLessEqual(d, 1.0)

    def test_signal_discount_monotonic(self):
        """折扣随排名递减"""
        from ml.bias_v_selector import _signal_discount
        for level in ["strong", "moderate", "weak"]:
            prev = 2.0
            for rank in range(1, 34):
                d = _signal_discount(rank, 15, level)
                self.assertLessEqual(d, prev, f"{level} rank={rank}")
                prev = d

    def test_signal_discount_none_returns_one(self):
        """无信号时折扣恒为 1.0"""
        from ml.bias_v_selector import _signal_discount
        for rank in range(1, 34):
            self.assertEqual(_signal_discount(rank, 15, "none"), 1.0)

    def test_signal_levels_produce_valid_ordering(self):
        """各信号级别的折扣函数都在合法范围且按预期方向衰减"""
        from ml.bias_v_selector import _signal_discount
        # 强信号衰减最慢: 在低排名处折扣应该最高
        for rank in [5, 10, 15, 20]:
            s = _signal_discount(rank, 20, "strong")
            m = _signal_discount(rank, 20, "moderate")
            w = _signal_discount(rank, 20, "weak")
            self.assertGreaterEqual(s, m, f"rank={rank}: strong >= moderate")
            self.assertGreaterEqual(m, w, f"rank={rank}: moderate >= weak")
        # 在排名足够大时, 所有折扣都应该衰减到接近0
        for level in ["strong", "moderate", "weak"]:
            d = _signal_discount(33, 20, level)
            self.assertLess(d, 0.5, f"rank=33 {level} should be < 0.5")

    def test_result_is_dataclass(self):
        """返回值是 BiasVResult"""
        from ml.bias_v_selector import auto_v, BiasVResult
        result = auto_v()
        self.assertIsInstance(result, BiasVResult)


if __name__ == "__main__":
    unittest.main()
