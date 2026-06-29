"""模块导入验证 — 确保所有活跃模块无 ImportError"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestImports(unittest.TestCase):
    """验证所有活跃模块可正常导入"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_ml_modules(self):
        """ml/ 下 5 个活跃模块"""
        from ml import micro_portfolio, covering_design, prize_evaluator, ssq_constants
        self.assertIsNotNone(micro_portfolio)
        self.assertIsNotNone(covering_design)
        self.assertIsNotNone(prize_evaluator)
        self.assertIsNotNone(ssq_constants)

    def test_server_modules(self):
        """server/ 下所有活跃模块"""
        from server import db, fetcher, handler, ml_bridge, recommend, weight_optimizer
        self.assertIsNotNone(db)
        self.assertIsNotNone(fetcher)
        self.assertIsNotNone(handler)
        self.assertIsNotNone(ml_bridge)
        self.assertIsNotNone(recommend)
        self.assertIsNotNone(weight_optimizer)

    def test_ml_bridge_active_functions(self):
        """ml_bridge 剩余活跃函数可正常导入"""
        from server.ml_bridge import micro_3_tickets, get_rule_status, generate_covering, evaluate_prizes
        self.assertTrue(callable(micro_3_tickets))
        self.assertTrue(callable(get_rule_status))
        self.assertTrue(callable(generate_covering))
        self.assertTrue(callable(evaluate_prizes))


if __name__ == "__main__":
    unittest.main()
