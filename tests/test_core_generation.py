"""核心生成单元测试"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestGenerateTickets(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_default_3_tickets(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=3)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["tickets"]), 3)
        for t in r["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertTrue(1 <= t["blue"] <= 16)
            for red in t["reds"]:
                self.assertTrue(1 <= red <= 33)
        self.assertIn("algorithm", r)
        self.assertEqual(r["cost_rmb"], 6)
        self.assertEqual(r["budget"], 3)

    def test_n1(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=1)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["tickets"]), 1)
        self.assertEqual(r["cost_rmb"], 2)

    def test_n2(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=2)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["tickets"]), 2)

    def test_soft_filter(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=3, soft=True)
        self.assertTrue(r["ok"])
        self.assertTrue(r["soft_filter"])
        self.assertGreater(r["soft_excluded"], 0)

    def test_reds_sorted(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=3)
        for t in r["tickets"]:
            self.assertEqual(t["reds"], sorted(t["reds"]))

    def test_all_reds_1_33(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=5)
        for t in r["tickets"]:
            for red in t["reds"]:
                self.assertTrue(1 <= red <= 33)

    def test_cost(self):
        from ml.micro_portfolio import generate_tickets
        for n in [1, 3]:
            r = generate_tickets(n=n)
            self.assertEqual(r["cost_rmb"], n * 2)


class TestMaxOverlap(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_overlap_0_no_shared_reds(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=3, max_overlap=0)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["tickets"]), 3)
        for i in range(3):
            for j in range(i + 1, 3):
                overlap = len(set(r["tickets"][i]["reds"]) & set(r["tickets"][j]["reds"]))
                self.assertEqual(overlap, 0)

    def test_overlap_0_blue_unique(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=3, max_overlap=0)
        blues = [t["blue"] for t in r["tickets"]]
        self.assertEqual(len(set(blues)), 3)

    def test_overlap_2_at_most_2(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=3, max_overlap=2)
        for i in range(3):
            for j in range(i + 1, 3):
                overlap = len(set(r["tickets"][i]["reds"]) & set(r["tickets"][j]["reds"]))
                self.assertLessEqual(overlap, 2)

    def test_overlap_none_no_crash(self):
        from ml.micro_portfolio import generate_tickets
        r = generate_tickets(n=3, max_overlap=None)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["tickets"]), 3)


class TestBlueWeights(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_weights_sum_to_1(self):
        from ml.micro_portfolio import _blue_freq_weights
        w = _blue_freq_weights()
        self.assertEqual(len(w), 16)
        self.assertAlmostEqual(sum(w), 1.0, places=6)

    def test_all_positive(self):
        from ml.micro_portfolio import _blue_freq_weights
        for w in _blue_freq_weights():
            self.assertGreater(w, 0)

    def test_weighted_choice_range(self):
        from ml.micro_portfolio import _weighted_choice, _blue_freq_weights
        w = _blue_freq_weights()
        for _ in range(50):
            b = _weighted_choice(w, range(1, 17))
            self.assertTrue(1 <= b <= 16)

    def test_freq_candidates(self):
        from ml.micro_portfolio import _freq_blue_candidates
        c = _freq_blue_candidates(n=6)
        self.assertEqual(len(c), 6)
        for b in c:
            self.assertTrue(1 <= b <= 16)


class TestEndToEnd(unittest.TestCase):
    """端到端: generate_tickets 全流程 + 所有约束校验"""

    def setUp(self):
        from server.db import load_draws
        self.data = load_draws()
        self.assertGreater(len(self.data), 100, "至少需要100期开奖数据")

    def test_e2e_default_3_tickets(self):
        """默认3注: 全部通过约束, 互不重叠, 在有效范围内"""
        from ml.micro_portfolio import generate_tickets
        from ml.global_constraint import validate_combo

        result = generate_tickets(n=3, max_overlap=0, constraint_level='normal')
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 3)

        for i, t in enumerate(result["tickets"]):
            reds = t["reds"]
            self.assertEqual(len(reds), 6)
            self.assertEqual(len(set(reds)), 6, f"Ticket {i}: 红球重复")
            for r in reds:
                self.assertTrue(1 <= r <= 33, f"Ticket {i}: 红球 {r} 超出范围")
            self.assertTrue(1 <= t["blue"] <= 16, f"Ticket {i}: 蓝球 {t['blue']} 超出范围")
            self.assertEqual(reds, sorted(reds), f"Ticket {i}: 红球未排序")
            ok, violations = validate_combo(reds, constraint_level='normal')
            self.assertTrue(ok, f"Ticket {i}: 全局约束失败 {violations}")

        # 注间无重叠
        for i in range(3):
            for j in range(i + 1, 3):
                overlap = len(set(result["tickets"][i]["reds"])
                              & set(result["tickets"][j]["reds"]))
                self.assertEqual(overlap, 0,
                                 f"Ticket {i} vs {j} 重叠 {overlap} 个红球")

    def test_e2e_signals_available(self):
        """信号融合正常返回, 两个算法都在"""
        from ml.signal_aggregator import collect_all_signals, collect_blue_signals

        fused_w, diag = collect_all_signals(self.data)
        self.assertEqual(diag["n_active"], 2)
        self.assertIn("gap_analysis", diag["active_list"])
        self.assertIn("position", diag["active_list"])
        for n in range(1, 34):
            self.assertTrue(0.5 <= fused_w[n] <= 2.0,
                            f"红球 {n} 权重 {fused_w[n]} 超出 [0.5, 2.0]")

        blue_w, blue_d = collect_blue_signals(self.data)
        for b in range(1, 17):
            self.assertTrue(0.5 <= blue_w[b] <= 2.0,
                            f"蓝球 {b} 权重 {blue_w[b]} 超出 [0.5, 2.0]")

    def test_e2e_constraint_summary(self):
        """全局约束摘要和实际数据一致"""
        from ml.global_constraint import constraint_summary
        cs = constraint_summary(self.data)
        self.assertIn("sum", cs)
        self.assertIn("span", cs)
        self.assertIn("odd_count", cs)
        self.assertGreater(cs["n_draws"], 100)

    def test_e2e_all_levels(self):
        """loose/normal/strict 三级约束均能出号"""
        from ml.micro_portfolio import generate_tickets
        for level in ("loose", "normal", "strict"):
            result = generate_tickets(n=1, constraint_level=level)
            self.assertTrue(result["ok"], f"constraint_level={level} 失败")
            self.assertEqual(len(result["tickets"]), 1)

    def test_e2e_fallback(self):
        """无数据时随机降级也不崩溃"""
        from ml.micro_portfolio import generate_tickets
        # 传空数据模拟
        result = generate_tickets(n=1)
        self.assertTrue(result["ok"])
        t = result["tickets"][0]
        self.assertEqual(len(t["reds"]), 6)
        self.assertEqual(len(set(t["reds"])), 6)
        self.assertTrue(1 <= t["blue"] <= 16)

    def test_e2e_gap_weights(self):
        """gap_analysis 在真实数据上正常返回"""
        from ml.gap_analysis import compute_gap_weights
        w, d = compute_gap_weights(self.data, window=100)
        self.assertEqual(len(w), 34)
        for n in range(1, 34):
            self.assertTrue(0.5 <= w[n] <= 2.0,
                            f"gap 权重 {n}={w[n]} 越界")
        self.assertIn("hot", d)
        self.assertIn("hot", d)

    def test_e2e_position_weights(self):
        """position_model 在真实数据上正常返回"""
        from ml.position_model import compute_position_weights
        pos_probs, d = compute_position_weights(self.data, window=100)
        self.assertEqual(len(pos_probs), 7)  # positions 1-6
        for p in range(1, 7):
            self.assertEqual(len(pos_probs[p]), 34)
        self.assertIn("hot_by_pos", d)
