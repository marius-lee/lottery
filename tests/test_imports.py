"""模块导入验证"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestImports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)

    def test_ml_modules(self):
        from ml import micro_portfolio, recent_bias
        self.assertIsNotNone(micro_portfolio)
        self.assertIsNotNone(recent_bias)

    def test_server_modules(self):
        from server import db, fetcher, handler
        self.assertIsNotNone(db)
        self.assertIsNotNone(fetcher)
        self.assertIsNotNone(handler)

    def test_generate_tickets(self):
        from ml.micro_portfolio import generate_tickets, rule_status
        self.assertTrue(callable(generate_tickets))
        self.assertTrue(callable(rule_status))


if __name__ == "__main__":
    unittest.main()
