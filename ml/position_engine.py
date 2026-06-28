"""分位置策略引擎 — 每位置独立最优方法选号.

封装 docs/research/position_engine.py 的研究原型,
提供 ml_bridge.py 可用的稳定接口.
"""
import sys, os
if str(os.path.join(os.path.dirname(__file__), '..', 'docs', 'research')) not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'docs', 'research'))

from position_engine import position_tickets

__all__ = ['position_tickets']
