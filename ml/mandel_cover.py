"""Mandel 全买覆盖引擎 — 枚举C(V,6)×16蓝球, 头奖触发.

数学基础 (Stömmer 2024, La Jolla Covering Repository):
  Stefan Mandel 的14次中奖策略: 选V个红球号码, 全买C(V,6)所有组合×16蓝球.
  - 若6个开奖红球全在V中 → 必有一注命中6红 → ×16蓝球 → 必中一等奖
  - 若5个开奖红球在V中 → 必有一注命中5红 → ×16蓝球 → 必中三等奖(¥3,000)

期望成本分析 (与V无关):
  期望总成本 = cost/draw / P(6红全在V)
  = C(V,6)×16×2 / (C(V,6)/C(33,6))
  = 32 × C(33,6) = 32 × 1,107,568 = ¥35,442,176

  所以保本头奖 = ¥3,544万 (任何V)

策略选择:
  - V=10: ¥6,720/期, 期望等待33.8年 (成本可控但极慢)
  - V=12: ¥29,568/期, 期望等待7.7年
  - V=14: ¥96,096/期, 期望等待2.4年
  - V=15: ¥160,160/期, 期望等待1.4年
"""

import math
import itertools
import random
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from ml.ssq_constants import TOTAL_RED, PICK_RED, TOTAL_BLUE, TICKET_PRICE, TOTAL_COMBOS_RED


@dataclass
class MandelConfig:
    """Mandel 策略参数."""
    v: int = 12                         # 选号池大小 (6-33)
    jackpot_threshold: float = 50_000_000  # 头奖触发阈值 (元)
    auto_trigger: bool = False           # 是否自动触发

    def __post_init__(self):
        if self.v < PICK_RED:
            raise ValueError(f"V 至少为 {PICK_RED}")
        if self.v > TOTAL_RED:
            raise ValueError(f"V 最大为 {TOTAL_RED}")

    @property
    def total_combos(self) -> int:
        """C(V, 6) 红球组合数."""
        return math.comb(self.v, PICK_RED)

    @property
    def total_tickets(self) -> int:
        """总注数 = C(V,6) × 16 蓝球."""
        return self.total_combos * TOTAL_BLUE

    @property
    def cost_per_draw(self) -> int:
        """每期成本 (元)."""
        return self.total_tickets * TICKET_PRICE

    @property
    def p_all6_reds_in_v(self) -> float:
        """P(6个开奖红球全在V中)."""
        return self.total_combos / TOTAL_COMBOS_RED

    @property
    def expected_draws_to_win(self) -> float:
        """期望等待期数 (几何分布)."""
        p = self.p_all6_reds_in_v
        return 1.0 / p if p > 0 else float('inf')

    @property
    def expected_years_to_win(self) -> float:
        """期望等待年数 (156期/年 = 3/周×52)."""
        return self.expected_draws_to_win / 156

    @property
    def expected_total_cost(self) -> float:
        """期望总投入 = 成本/期 × 期望等待期数."""
        return self.cost_per_draw * self.expected_draws_to_win

    def to_dict(self) -> dict:
        return {
            "v": self.v,
            "total_combos": self.total_combos,
            "total_tickets": self.total_tickets,
            "cost_per_draw": self.cost_per_draw,
            "p_all6_reds_pct": round(self.p_all6_reds_in_v * 100, 4),
            "expected_draws": round(self.expected_draws_to_win, 0),
            "expected_years": round(self.expected_years_to_win, 1),
            "expected_total_cost": round(self.expected_total_cost, 0),
            "jackpot_threshold": self.jackpot_threshold,
            "breakeven_jackpot": 35442176,  # 32*C(33,6)
        }


def select_v_numbers(data: List, v: int = 12, method: str = "frequency") -> List[int]:
    """选V个号码.

    Args:
        data: 历史开奖数据
        v: 号码池大小
        method: 选号策略
          - "frequency": Laplace平滑频率 (默认)
          - "random": 纯随机
          - "cold9": 吴明冷号反转
          - "ensemble": 多方法加权聚合

    Returns:
        选中的V个号码 (1-indexed, 升序)
    """
    if method == "random":
        return sorted(random.sample(range(1, 34), v))

    if method == "laplace":
        # Laplace平滑频率
        counts = [1.0] * 33
        for row in data:
            for n in row[1:7]:
                counts[n - 1] += 1.0
        ranked = sorted(range(1, 34), key=lambda x: -counts[x - 1])
        return sorted(ranked[:v])

    if method == "cold9":
        # 冷号反转: 遗漏9-20期的号码优先
        from ml.micro_portfolio import _period9_cold
        result = _period9_cold()
        cold_candidates = []
        if result.get("ok"):
            for c in result.get("cold_numbers", []):
                n = c["number"]
                om = c["omission"]
                if 9 <= om <= 20:
                    cold_candidates.append(n)
        # 补充频率top
        counts = [0] * 33
        for row in data[-200:]:
            for n in row[1:7]:
                counts[n - 1] += 1
        for n in sorted(range(1, 34), key=lambda x: -counts[x - 1]):
            if n not in cold_candidates and len(cold_candidates) < v:
                cold_candidates.append(n)
        return sorted(cold_candidates[:v])

    if method == "ensemble":
        # 5方法加权聚合
        from ml.ensemble_aggregator import (
            _init_registry, score_all_methods, aggregate_scores, _get_weights
        )
        _init_registry()
        weights = _get_weights(data, k=v)
        method_scores = score_all_methods(data)
        final = aggregate_scores(method_scores, weights)
        ranked = sorted(range(1, 34), key=lambda x: -final[x - 1])
        return sorted(ranked[:v])

    # Default: frequency
    return select_v_numbers(data, v, "laplace")


def generate_all_tickets(v_numbers: List[int]) -> List[Dict]:
    """枚举所有 C(V,6) × 16 蓝球 = 全买.

    Args:
        v_numbers: V个红球号码 (升序)

    Returns:
        [{reds: [int×6], blue: int}, ...] 全部 C(V,6)×16 注
    """
    tickets = []
    for reds in itertools.combinations(sorted(v_numbers), 6):
        for blue in range(1, TOTAL_BLUE + 1):
            tickets.append({"reds": list(reds), "blue": blue})
    return tickets


def generate(mandel_config: MandelConfig,
             selection_method: str = "laplace") -> Dict:
    """Mandel 全买出号 — 枚举所有C(V,6)×16蓝球.

    Args:
        mandel_config: Mandel策略参数
        selection_method: 号码选择方法

    Returns:
        dict with tickets, cost, probability analysis, jackpot check
    """
    from server.db import load_draws
    data = load_draws()

    v_numbers = select_v_numbers(data, mandel_config.v, selection_method)
    tickets = generate_all_tickets(v_numbers)

    config_info = mandel_config.to_dict()
    config_info["selection_method"] = selection_method
    config_info["v_numbers"] = v_numbers

    # 头奖检查
    jackpot = _fetch_jackpot()
    trigger = jackpot >= mandel_config.jackpot_threshold if jackpot else None

    # 期望价值计算
    ev_first = mandel_config.p_all6_reds_in_v * jackpot if jackpot else 0
    ev_per_draw = ev_first + _estimate_lower_prizes(v_numbers) * 16  # ×16 blues
    ev_ratio = ev_per_draw / mandel_config.cost_per_draw if mandel_config.cost_per_draw > 0 else 0

    return {
        "ok": True,
        "algorithm": f"Mandel-FullCover-v{mandel_config.v}",
        "config": config_info,
        "tickets": tickets,
        "total_tickets": len(tickets),
        "cost_rmb": mandel_config.cost_per_draw,
        "jackpot": {
            "current": jackpot or 0,
            "threshold": mandel_config.jackpot_threshold,
            "trigger": trigger,
            "source": "内存缓存" if jackpot else "数据未拉取",
        },
        "probability": {
            "p_all6_reds": round(mandel_config.p_all6_reds_in_v * 100, 4),
            "guarantee": (f"若6个开奖红球全在{mandel_config.v}个号码中({v_numbers}): "
                         "必中一等奖(6+1) — 蓝球全买16个, 必有一注蓝球命中"),
        },
        "ev_estimate": {
            "ev_per_draw": round(ev_per_draw, 2),
            "cost_per_draw": mandel_config.cost_per_draw,
            "ev_ratio": round(ev_ratio, 4),
            "verdict": "positive" if ev_ratio > 1 else ("breakeven" if ev_ratio > 0.8 else "negative"),
            "note": f"保本头奖=¥3,544万, 当前头奖={jackpot or '未知'}",
        },
        "warning": (
            f"⚠ 每期 ¥{mandel_config.cost_per_draw:,}, 期望等{mandel_config.expected_years_to_win:.1f}年, "
            f"总期望投入 ¥{mandel_config.expected_total_cost:,.0f}"
        ),
    }


def _fetch_jackpot() -> Optional[float]:
    """拉取当前双色球头奖金额."""
    try:
        import json, ssl, urllib.request, http.cookiejar

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.HTTPCookieProcessor(cj),
        )

        url = ("https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/"
               "findDrawNotice?name=ssq&issueCount=1")
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.cwl.gov.cn/ygkj/ssq/kjgg/",
        })
        resp = opener.open(req, timeout=10)
        body = json.loads(resp.read().decode("utf-8"))

        items = body.get("result", body.get("data", []))
        if isinstance(items, dict):
            items = items.get("list", items.get("records", []))
        if isinstance(items, list) and items:
            # 尝试多个可能的字段名
            item = items[0]
            for key in ["prizeMoney", "prize1Money", "jackpot", "firstPrize"]:
                val = item.get(key)
                if val:
                    return float(val)
        return None
    except Exception:
        return None


def _estimate_lower_prizes(v_numbers: List[int]) -> float:
    """估算单蓝球下低等奖的期望收益.

    当5红在V中 → 必中三等奖(¥3,000)
    当4红在V中 → 必中五等奖(¥10)(4+0) 或四等奖(¥200)(4+1)
    """
    from ml.ssq_constants import PRIZE_3RD, PRIZE_4TH, PRIZE_5TH, PRIZE_6TH, BLUE_HIT_PROB
    v = len(v_numbers)

    p_5inV = math.comb(v, 5) * math.comb(33 - v, 1) / math.comb(33, 6)
    p_4inV = math.comb(v, 4) * math.comb(33 - v, 2) / math.comb(33, 6)
    p_3inV = math.comb(v, 3) * math.comb(33 - v, 3) / math.comb(33, 6)

    # 当至少4红在V中 + 本注蓝球也中:
    ev = (p_5inV * PRIZE_3RD +
          p_4inV * PRIZE_4TH * BLUE_HIT_PROB +
          p_4inV * PRIZE_5TH * (1 - BLUE_HIT_PROB) +
          p_3inV * PRIZE_6TH * BLUE_HIT_PROB)

    return ev


def mandel_summary() -> List[Dict]:
    """生成 V=8~15 的完整对比表 (供前端渲染)."""
    rows = []
    for v in range(8, 16):
        cfg = MandelConfig(v=v)
        d = cfg.to_dict()
        d["weekly_cost"] = d["cost_per_draw"] * 3  # ~3 draws/week
        rows.append(d)
    return rows
