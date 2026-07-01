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
