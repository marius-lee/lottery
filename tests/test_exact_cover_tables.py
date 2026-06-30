"""La Jolla 精确覆盖表测试 — exact_cover_tables.py"""
import unittest
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLaJollaTables(unittest.TestCase):
    """验证 La Jolla C(v,6,4) 完整覆盖表"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_all_tables_100_percent_cover(self):
        """所有 v 的表都是 100% 4-子集覆盖"""
        from ml.exact_cover_tables import FULL_COVERS, verify_cover
        for v in [12, 13, 14, 15, 16]:
            table = FULL_COVERS[(v, 4)]
            self.assertGreater(len(table), 0, f"v={v} table is empty")
            result = verify_cover(table, v, t=4)
            self.assertEqual(
                result["uncovered"], 0,
                f"v={v}: {result['uncovered']} t-subsets uncovered"
            )
            self.assertEqual(result["coverage_pct"], 100.0)

    def test_tables_match_schonheim_lower_bound(self):
        """表注数 >= Schonheim 数学下界"""
        from ml.exact_cover_tables import FULL_COVERS, schonheim_bound
        for v in [12, 13, 14, 15, 16]:
            table = FULL_COVERS[(v, 4)]
            lb = schonheim_bound(v)
            self.assertGreaterEqual(
                len(table), lb,
                f"v={v}: {len(table)} tickets < Schonheim lower bound {lb}"
            )

    def test_all_tickets_are_valid(self):
        """每注都是 6 个 1..v 范围内的不同号码"""
        from ml.exact_cover_tables import FULL_COVERS
        for v in [12, 13, 14, 15, 16]:
            table = FULL_COVERS[(v, 4)]
            for i, ticket in enumerate(table):
                self.assertEqual(len(ticket), 6, f"v={v} ticket#{i}")
                self.assertEqual(len(set(ticket)), 6, f"v={v} ticket#{i} has duplicates")
                for num in ticket:
                    self.assertGreaterEqual(num, 1, f"v={v} ticket#{i}")
                    self.assertLessEqual(num, v, f"v={v} ticket#{i}")

    def test_take_top_n_returns_correct_count(self):
        """take_top_n 返回恰好 n 注"""
        from ml.exact_cover_tables import take_top_n
        for v in [12, 13, 14, 15, 16]:
            for n in [3, 6, 10]:
                result = take_top_n(v, 4, n)
                self.assertIsNotNone(result)
                self.assertEqual(len(result), n)

    def test_take_top_n_maps_hot_numbers_correctly(self):
        """take_top_n 正确映射到指定热号"""
        from ml.exact_cover_tables import take_top_n
        hot = [5, 10, 15, 20, 25, 30, 1, 6, 11, 16, 21, 26]
        result = take_top_n(12, 4, 3, hot_numbers=hot)
        self.assertIsNotNone(result)
        for ticket in result:
            for num in ticket:
                self.assertIn(num, hot[:12])

    def test_take_top_n_unknown_v_returns_none(self):
        """不存在的 v 返回 None"""
        from ml.exact_cover_tables import take_top_n
        result = take_top_n(33, 4, 3)
        self.assertIsNone(result)

    def test_verify_cover_with_partial_table(self):
        """部分覆盖的验证正确"""
        from ml.exact_cover_tables import verify_cover
        # v=12, take first ticket only - should have very low coverage
        from ml.exact_cover_tables import C12_6_4
        result = verify_cover([C12_6_4[0]], 12, t=4)
        self.assertLess(result["coverage_pct"], 30)
        self.assertGreater(result["uncovered"], 0)


class TestLaJollaIntegration(unittest.TestCase):
    """整合 exact_cover 使用 La Jolla 表"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_exact_cover_uses_la_jolla_for_v12_14(self):
        """exact_cover 对 v=12-14 使用 La Jolla 表"""
        from ml.exact_cover import exact_cover
        for v in [12, 13, 14]:
            result = exact_cover(v=v, t=4, n=3)
            self.assertTrue(result.ok)
            self.assertIn("La Jolla", result.source)
            self.assertEqual(len(result.tickets), 3)

    def test_exact_cover_with_hot_number_mapping(self):
        """exact_cover 正确映射热号"""
        from ml.exact_cover import exact_cover
        hot = [7, 14, 21, 28, 3, 10, 17, 24, 31, 6, 13, 20]
        result = exact_cover(v=12, t=4, n=3, hot_numbers=hot)
        self.assertTrue(result.ok)
        for ticket in result.tickets:
            for num in ticket:
                self.assertIn(num, hot[:12])


if __name__ == "__main__":
    unittest.main()
