"""测试张委铭算法模块"""
import sys
sys.path.insert(0, '.')
import pytest
from ml.zhang_weiming import (
    _map_to_red, _map_to_blue,
    _compute_weihao_values, _compute_weihao_blue_values,
    generate_weihao, generate_weihao_blue, generate_combined,
    _RED_KILL_METHODS_18, _BLUE_KILL_METHODS_10,
)


class TestKillMapping:
    """杀号规则映射测试"""

    def test_map_to_red_in_range(self):
        assert _map_to_red(17) == 17
        assert _map_to_red(1) == 1
        assert _map_to_red(33) == 33

    def test_map_to_red_wrap(self):
        # 新规则: >33取个位数, 0→10 (原书p238示例验证)
        assert _map_to_red(34) == 4   # 个位4
        assert _map_to_red(35) == 5   # 个位5
        assert _map_to_red(40) == 10  # 个位0→10

    def test_map_to_red_negative(self):
        assert _map_to_red(-10) == 10   # |−10|=10, ≤33直接
        assert _map_to_red(-29) == 29   # |−29|=29, ≤33直接 (书中I32示例)
        assert _map_to_red(-58) == 8    # |−58|=58>33, 个位8 (书中C4-68示例)
        assert _map_to_red(-64) == 4    # |−64|=64>33, 个位4 (书中C1-68示例)

    def test_map_to_blue_in_range(self):
        for n in range(1, 17):
            assert _map_to_blue(n) == n

    def test_map_to_blue_large(self):
        # 个位数规则: 24→4, 19→9, 36→6 (原书验证)
        assert _map_to_blue(24) == 4
        assert _map_to_blue(19) == 9
        assert _map_to_blue(36) == 6
        assert _map_to_blue(20) == 10  # 个位0→10

    def test_map_to_blue_negative(self):
        assert _map_to_blue(-10) == 10


class TestWeihaoBlue:
    """后区围号选号法测试 (2017版)"""

    def test_10_methods_defined(self):
        assert len(_BLUE_KILL_METHODS_10) == 10

    def test_generate_runs(self):
        """确保生成函数不崩溃"""
        from server.db import load_draws
        data = load_draws()
        if len(data) >= 5:
            result = generate_weihao_blue(data, n_tickets=2)
            assert result["ok"]
            assert result["candidate_count"] >= 1
            assert len(result["tickets"]) == 2


class TestWeihao:
    """围号选号法测试 (2017版)"""

    def test_18_methods_defined(self):
        assert len(_RED_KILL_METHODS_18) == 18

    def test_generate_runs(self):
        from server.db import load_draws
        data = load_draws()
        if len(data) >= 5:
            result = generate_weihao(data, n_tickets=2)
            assert result["ok"]
            assert result["candidate_count"] >= 6
            assert len(result["tickets"]) == 2

    def test_combined_runs(self):
        from server.db import load_draws
        data = load_draws()
        if len(data) >= 5:
            result = generate_combined(data, n_tickets=2)
            assert result["ok"]
            assert result["weihao"]["candidate_count"] >= 6
            assert result["weihao_blue"]["candidate_count"] >= 1
