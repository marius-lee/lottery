"""SPRT 序贯概率比检验 (Wald, 1945)

实时监控: "当前策略是否开始偏离随机期望?"

在线检测 (每期更新):
  1. 建立假设 H0: 中奖率 = 基线 (随机期望)
  2. 每期计算 LLR (对数似然比)
  3. 当 LLR > α阈值 → 拒绝H0 → 信号: 策略优于随机? 或异常?
  4. 当 LLR < β阈值 → 接受H0 → 无差异

用途:
  - 策略评估: 区分"偶尔连中"和"真实优势"
  - 早期预警: 策略连续失败 → 调整或停止
  - 头奖触发: 当池子缩小+正面信号累积 → 加大投入
"""
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# Wald 阈值 (经典值)
ALPHA = 0.05  # Type-I error: 假阳性 (误判有效)
BETA = 0.10   # Type-II error: 假阴性 (漏判有效)
A = (1 - BETA) / ALPHA      # 接受H0上界
B = BETA / (1 - ALPHA)      # 拒绝H0下界


@dataclass
class SPRTState:
    llr: float = 0.0          # 累计对数似然比
    n: int = 0                # 观测期数
    hits: int = 0             # 命中次数
    threshold_upper: float = math.log(A)
    threshold_lower: float = math.log(B)
    status: str = "ongoing"   # ongoing | significant | not_significant
    history: List[dict] = field(default_factory=list)

    def update(self, hit: bool, p_alt: float, p_null: float):
        """更新SPRT: 观测一个二元结果.

        Args:
            hit: 是否命中 (True=中奖, False=未中)
            p_alt: 备择假设下的命中率 (策略声称的)
            p_null: 原假设下的命中率 (随机基线)
        """
        if not (0 < p_alt < 1 and 0 < p_null < 1):
            return
        if p_alt == p_null:
            return

        self.n += 1
        if hit:
            self.hits += 1
            self.llr += math.log(p_alt / p_null)
        else:
            self.llr += math.log((1 - p_alt) / (1 - p_null))

        self.history.append({
            "n": self.n, "hit": hit, "llr": round(self.llr, 4),
            "cumulative_hit_rate": round(self.hits / self.n, 4),
        })

        if self.llr >= self.threshold_upper:
            self.status = "significant"  # 拒绝H0: 策略优于随机
        elif self.llr <= self.threshold_lower:
            self.status = "not_significant"  # 接受H0: 无差异

    def summary(self):
        return {
            "n": self.n,
            "hits": self.hits,
            "hit_rate": round(self.hits / self.n, 4) if self.n > 0 else 0,
            "llr": round(self.llr, 4),
            "threshold_upper": round(self.threshold_upper, 4),
            "threshold_lower": round(self.threshold_lower, 4),
            "status": self.status,
            "interpretation": {
                "significant": "H0被拒绝 — 观测结果显著偏离随机基线 (可能优于或劣于)",
                "not_significant": "H0被接受 — 无证据偏离随机基线",
                "ongoing": "仍需更多数据",
            }.get(self.status, ""),
        }


def monitor_red_hits(actual_hits_per_draw: List[int],
                     pool_v: int = 15,  # [工程] 回退默认值, 实际由 auto_v() 动态确定
                     p_alt_lift: float = 1.1):
    """监控红球命中率的SPRT.

    Args:
        actual_hits_per_draw: 每期实际命中红球数 [2, 1, 3, ...]
        pool_v: 号码池大小
        p_alt_lift: 备择假设lift倍数 (1.1 = 10%优于随机)

    Returns:
        SPRTState summary
    """
    # 随机基线: 若池中有v个号, 每注期望命中 = 6 × v/33
    baseline_per_ticket = 6 * pool_v / 33
    # 转为"单期观测至少命中K个"的概率
    K = 2  # 备择命中数 [数学]: 若池大小v与覆盖设计有效, 每注期望 ≥ baseline+σ
    p_null = 1 - sum(
        math.comb(6, k) * (pool_v/33)**k * ((33-pool_v)/33)**(6-k)
        for k in range(K)
    )  # P(≥K命中)

    p_alt = min(p_null * p_alt_lift, 0.999)

    state = SPRTState()
    for h in actual_hits_per_draw:
        state.update(h >= K, p_alt, p_null)

    return state.summary()


def monitor_blue_hits(blue_results: List[bool],
                      pool_size: int = 6,  # [工程] 蓝球缩小池默认 top-6 (命中率 ~37.5% = 6/16)
                      p_alt_lift: float = 1.2):
    """监控蓝球命中率.

    Args:
        blue_results: 每期蓝球是否命中 [True, False, True, ...]
        pool_size: 蓝池大小
        p_alt_lift: 备择lift

    Returns:
        SPRTState summary
    """
    p_null = pool_size / 16  # 随机命中率
    p_alt = min(p_null * p_alt_lift, 0.999)

    state = SPRTState()
    for hit in blue_results:
        state.update(hit, p_alt, p_null)

    return state.summary()


def expected_sample_size(p_null, p_alt, alpha=ALPHA, beta=BETA):
    """Wald近似: SPRT达到决策的期望期数.

    用于预估需要多少期数据才能做出统计判断.

    Returns:
        {"E[N|H0]": xxx, "E[N|H1]": yyy}
    """
    if p_null == p_alt:
        return {"error": "p_null = p_alt, 无差异可检测"}

    c1 = math.log((1 - beta) / alpha)
    c2 = math.log(beta / (1 - alpha))
    e_h0 = (1 / p_null) * (c1 * (1 - beta) + c2 * beta)  # 近似
    e_h1 = (1 / p_alt) * (c1 * beta + c2 * (1 - beta))  # 近似

    return {
        "expected_under_null": round(e_h0, 1),
        "expected_under_alt": round(e_h1, 1),
        "interpretation": f"约需{e_h1:.0f}期可做出判断",
    }
