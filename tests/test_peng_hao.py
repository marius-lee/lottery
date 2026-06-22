"""彭浩算法单元测试 — peng_hao.py"""
import unittest
import sys
import os
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_data(n_periods=30):
    """生成 n_periods 期模拟双色球数据 [period, r1..r6, blue]."""
    rng = random.Random(42)  # 固定种子可重复
    data = []
    for i in range(n_periods):
        period = 2026001 + i
        reds = sorted(rng.sample(range(1, 34), 6))
        blue = rng.randint(1, 16)
        data.append([period] + reds + [blue])
    return data


class TestNumberChannel(unittest.TestCase):
    """通道计算测试"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_channel_needs_min_data(self):
        """数据不足: 少于19期返回错误"""
        from ml.peng_hao import compute_channel
        data = _make_data(10)
        result = compute_channel(data, position=0)
        self.assertFalse(result["ok"])
        self.assertIn("数据不足", result["msg"])

    def test_channel_returns_all_fields(self):
        """19期+数据: 返回完整通道字段"""
        from ml.peng_hao import compute_channel
        data = _make_data(25)
        result = compute_channel(data, position=0)
        self.assertTrue(result["ok"])
        for field in ["ma", "sigma", "sigma_short", "upper", "lower",
                      "mid_upper", "mid_lower", "current", "band_width",
                      "accuracy_1", "position_name"]:
            self.assertIn(field, result, f"缺少字段: {field}")

    def test_channel_band_ordering(self):
        """通道5条均线顺序: upper > mid_upper > ma > mid_lower > lower"""
        from ml.peng_hao import compute_channel
        data = _make_data(50)
        for pos in range(7):
            result = compute_channel(data, position=pos)
            self.assertGreaterEqual(result["upper"], result["mid_upper"])
            self.assertGreaterEqual(result["mid_upper"], result["ma"])
            self.assertGreaterEqual(result["ma"], result["mid_lower"])
            self.assertGreaterEqual(result["mid_lower"], result["lower"])

    def test_channel_all_positions(self):
        """所有7个位置都能计算通道"""
        from ml.peng_hao import compute_all_channels
        data = _make_data(30)
        channels = compute_all_channels(data)
        self.assertEqual(len(channels), 7)
        for key in [f"pos_{i}" for i in range(7)]:
            self.assertIn(key, channels)
            self.assertTrue(channels[key]["ok"])

    def test_channel_accuracy_in_range(self):
        """accuracy_1 在 [0, 1] 范围内"""
        from ml.peng_hao import compute_channel
        data = _make_data(30)
        result = compute_channel(data, position=3)
        self.assertGreaterEqual(result["accuracy_1"], 0.0)
        self.assertLessEqual(result["accuracy_1"], 1.0)


class TestDirectionClassification(unittest.TestCase):
    """三方向/九方向分类测试"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_3_direction_up(self):
        """本期>上期 → 上"""
        from ml.peng_hao import classify_3_direction
        result = classify_3_direction([10, 12, 15])
        self.assertEqual(result["direction"], "up")
        self.assertEqual(result["code"], 9)

    def test_3_direction_down(self):
        """本期<上期 → 下"""
        from ml.peng_hao import classify_3_direction
        result = classify_3_direction([10, 12, 8])
        self.assertEqual(result["direction"], "down")
        self.assertEqual(result["code"], 1)

    def test_3_direction_flat(self):
        """本期=上期 → 平"""
        from ml.peng_hao import classify_3_direction
        result = classify_3_direction([10, 12, 12])
        self.assertEqual(result["direction"], "flat")
        self.assertEqual(result["code"], 5)

    def test_3_direction_insufficient_data(self):
        """数据不足时返回未知"""
        from ml.peng_hao import classify_3_direction
        result = classify_3_direction([10])
        self.assertIsNone(result["direction"])

    def test_9_direction_reversal(self):
        """下上=反转模式(code=3)"""
        from ml.peng_hao import classify_9_direction
        result = classify_9_direction([10, 8, 12])  # 先下后上
        self.assertEqual(result["code"], 3)
        self.assertTrue(result["reversal"])

    def test_9_direction_continuation(self):
        """下下=持续模式(code=1)"""
        from ml.peng_hao import classify_9_direction
        result = classify_9_direction([12, 8, 5])  # 连续下
        self.assertEqual(result["code"], 1)
        self.assertFalse(result["reversal"])


class TestDirectionTransition(unittest.TestCase):
    """转移概率矩阵测试"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_transition_matrix_normalized(self):
        """每个方向的转移概率之和≈1.0"""
        from ml.peng_hao import direction_transition_matrix
        data = _make_data(100)
        for pos in range(3):
            result = direction_transition_matrix(data, position=pos)
            self.assertTrue(result["ok"])
            for d in ["下", "平", "上"]:
                probs = result["transition_probs"][d]
                total = sum(probs.values())
                if total > 0:
                    self.assertAlmostEqual(total, 1.0, delta=0.01)

    def test_transition_has_prediction(self):
        """转移矩阵能给出方向预测"""
        from ml.peng_hao import direction_transition_matrix
        data = _make_data(50)
        result = direction_transition_matrix(data, position=0)
        self.assertIn("predicted_next", result)


class TestExtremeRules(unittest.TestCase):
    """极端值规则测试"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_red6_extreme_triggers_alert(self):
        """红六球≥30触发向下告警"""
        from ml.peng_hao import extreme_rules
        # 最后一期为data[-1], 红六球=33触发告警
        data = [[2026001, 1, 2, 3, 4, 5, 6, 8],
                [2026002, 5, 10, 15, 20, 25, 33, 9]]
        result = extreme_rules(data)
        self.assertTrue(result["ok"])
        alerts = [a for a in result["alerts"] if a["position"] == "红六球"]
        self.assertEqual(len(alerts), 1, f"应有1个红六球告警, 实际{len(alerts)}个")
        self.assertEqual(alerts[0]["predicted"], "下")

    def test_red1_extreme_triggers_alert(self):
        """红一球≤3触发向上告警"""
        from ml.peng_hao import extreme_rules
        # 最后一期红一球=1, 触发告警
        data = [[2026001, 5, 10, 15, 20, 25, 30, 8],
                [2026002, 1, 6, 12, 18, 24, 30, 9]]
        result = extreme_rules(data)
        self.assertTrue(result["ok"])
        alerts = [a for a in result["alerts"] if a["position"] == "红一球"]
        self.assertEqual(len(alerts), 1, f"应有1个红一球告警, 实际{len(alerts)}个")
        self.assertEqual(alerts[0]["predicted"], "上")


class TestGenerateTickets(unittest.TestCase):
    """出号测试"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_generate_needs_min_data(self):
        """数据不足时返回错误"""
        from ml.peng_hao import generate_tickets
        data = _make_data(10)
        result = generate_tickets(data, n=3)
        self.assertFalse(result["ok"])

    def test_generate_default_3_tickets(self):
        """默认生成3注完整票"""
        from ml.peng_hao import generate_tickets
        data = _make_data(30)
        result = generate_tickets(data, n=3)
        self.assertTrue(result["ok"], f"生成失败: {result.get('msg', '')}")
        self.assertEqual(len(result["tickets"]), 3)
        for t in result["tickets"]:
            self.assertEqual(len(t["reds"]), 6)
            self.assertGreaterEqual(t["blue"], 1)
            self.assertLessEqual(t["blue"], 16)
            # 红球升序
            self.assertEqual(t["reds"], sorted(t["reds"]))
            # 无重复
            self.assertEqual(len(set(t["reds"])), 6)
        # 蓝球不重复
        blues = [t["blue"] for t in result["tickets"]]
        self.assertEqual(len(blues), len(set(blues)))

    def test_generate_includes_channels(self):
        """返回包含通道摘要"""
        from ml.peng_hao import generate_tickets
        data = _make_data(30)
        result = generate_tickets(data, n=2)
        self.assertIn("channels", result)
        self.assertEqual(len(result["channels"]), 7)

    def test_generate_includes_extreme_alerts(self):
        """返回包含极端值告警"""
        from ml.peng_hao import generate_tickets
        data = _make_data(30)
        result = generate_tickets(data, n=2)
        self.assertIn("extreme_alerts", result)

    def test_generate_algorithm_name(self):
        """算法名包含'彭浩'"""
        from ml.peng_hao import generate_tickets
        data = _make_data(30)
        result = generate_tickets(data, n=1)
        self.assertIn("彭浩", result["algorithm"])

    def test_generate_different_n(self):
        """n=5生成5注"""
        from ml.peng_hao import generate_tickets
        data = _make_data(50)
        result = generate_tickets(data, n=5)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["tickets"]), 5)


if __name__ == "__main__":
    unittest.main()
