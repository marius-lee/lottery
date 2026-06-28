"""Black-Litterman 融合 — 多方法观点贝叶斯融合模块.

封装 docs/research/black_litterman.py 的研究原型,
提供 ml_bridge.py 可用的稳定接口.
"""
import sys, os
_sys_path_added = False
if str(os.path.join(os.path.dirname(__file__), '..', 'docs', 'research')) not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'docs', 'research'))
    _sys_path_added = True

from black_litterman import bl_tickets

__all__ = ['bl_tickets']
