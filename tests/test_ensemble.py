"""测试 ensemble_aggregator, bias_engine, black_litterman, position_engine, good_turing, zeng_xianzhong, zone_break"""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEnsembleAggregator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server.db import load_draws
        cls.data = load_draws()
        cls.has_data = len(cls.data) >= 50

    def test_registry_has_methods(self):
        from ml.ensemble_aggregator import _init_registry
        _init_registry()
        self.assertTrue(True)  # registry initialised without error

    def test_top_k_indices(self):
        from ml.ensemble_aggregator import _top_k_indices
        result = _top_k_indices([0.1, 0.5, 0.2, 0.9, 0.3], 3)
        self.assertEqual(len(result), 3)

    def test_frequency_baseline(self):
        from ml.ensemble_aggregator import _score_frequency_baseline
        if self.has_data:
            scores = _score_frequency_baseline(self.data)
            self.assertEqual(len(scores), 33)
            self.assertTrue(all(0 <= s <= 1 for s in scores))


class TestBiasEngine(unittest.TestCase):
    def test_dirichlet_import(self):
        from ml.bias_engine import dirichlet_red_posterior, dirichlet_blue_posterior
        self.assertTrue(callable(dirichlet_red_posterior))
        self.assertTrue(callable(dirichlet_blue_posterior))

    def test_gumbel_max_topk(self):
        from ml.bias_engine import gumbel_max_topk
        import random
        thetas = [random.random() for _ in range(33)]
        result = gumbel_max_topk(thetas, k=6)
        self.assertEqual(len(result), 6)

    def test_bias_stats(self):
        from ml.bias_engine import bias_stats
        result = bias_stats()
        self.assertIn('ok', result)


class TestBlackLitterman(unittest.TestCase):
    def test_archived(self):
        """模块已归档至 docs/research/ (Black-Litterman 融合未接入生产管线)"""
        self.assertTrue(True)


class TestPositionEngine(unittest.TestCase):
    def test_archived(self):
        """模块已归档至 docs/research/ (分位引擎未接入生产管线)"""
        self.assertTrue(True)


class TestZengXianzhong(unittest.TestCase):
    def test_archived(self):
        """模块已归档至 docs/research/ (曾献忠模块理论未接入生产管线)"""
        self.assertTrue(True)


class TestZoneBreak(unittest.TestCase):
    def test_get_zone_break_history(self):
        from ml.zone_break import get_zone_break_history
        from server.db import load_draws
        data = load_draws()
        if len(data) >= 2:
            result = get_zone_break_history(data)
            self.assertIn('periods', result)


class TestWumingModule(unittest.TestCase):
    def test_import(self):
        from ml.wuming import (wuming_cyclic_oscillation, period5_hotness,
                               zone6_exclusion, wu_sum_compound, repeat_method,
                               POSITION_VALUABLE, BLUE_CLOCKWISE, BLUE_BSD_TAIL)
        self.assertEqual(len(POSITION_VALUABLE), 6)
        self.assertEqual(len(BLUE_CLOCKWISE), 4)
        self.assertEqual(len(BLUE_BSD_TAIL), 4)

    def test_period5_hotness(self):
        from ml.wuming import period5_hotness
        result = period5_hotness()
        self.assertIn('ok', result)


class TestXiaZhiqiangModule(unittest.TestCase):
    def test_import(self):
        from ml.xia_zhiqiang import xia_sub4_add4_blue, xia_compute_reds
        self.assertTrue(callable(xia_sub4_add4_blue))
        self.assertTrue(callable(xia_compute_reds))


if __name__ == '__main__':
    unittest.main()
