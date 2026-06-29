"""实验1: 通用压缩测试 — 验证彩票序列是否有可压缩结构

原理: Kolmogorov复杂度 ≤ LZMA压缩长度。真随机序列不可压缩。
如果LZMA压缩率超过理论熵下限, 序列一定有非随机结构。

理论基准:
  - 每期 6红+1蓝: log2(C(33,6)×16) ≈ 24.08 bits [数学: Shannon源编码定理]
  - 2000期: 24.08 × 2000 = 48,160 bits ≈ 6,020 bytes 熵下限
  - 若压缩后 < 6,000 bytes → 序列可压缩 → 非随机

LZ77检验定理 (Ryabko+2024, arXiv:2105.06638):
  统计量 τ = n - |LZ(y)|
  拒绝域 τ > n - log(1/α) - 1
  α=0.01 → 阈值 = n - log(100) - 1 ≈ n - 7.6

编码:
  方式A: 二进制位掩码 — 33位红球+16位蓝球 = 49 bits/draw
  方式B: 号码差值 — 相邻期各位置号码变化量
  方式C: 原始号码 — 每个号码1字节
  方式D: 字典编码 — 每注映射为17位ID (log2(1,107,568×16) ≈ 24)
"""
import lzma
import struct
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_data():
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════════════
# 编码方式
# ═══════════════════════════════════════════════════════════════════

def encode_bitmask(data):
    """方式A: 位掩码. 每期 33+16=49 bits, 7 bytes/期.
    2000期 ≈ 14KB 原始."""
    result = bytearray()
    for row in data:
        red_mask = 0
        for n in row[1:7]:
            red_mask |= 1 << (n - 1)
        blue_bits = row[7] - 1  # 0-15
        # 33位红球 + 8位蓝球 = 41位≈6字节
        combined = (red_mask << 8) | blue_bits
        result.extend(struct.pack('>Q', combined)[2:])  # 低6字节
    return bytes(result)


def encode_positions(data):
    """方式B: 位置序列. 每期6个红球位置(0-32各1字节)+1蓝球位置.
    7 bytes/期, 2000期 ≈ 14KB."""
    result = bytearray()
    for row in data:
        reds = sorted(row[1:7])
        for r in reds:
            result.append(r - 1)  # 0-32
        result.append(row[7] - 1)  # 0-15
    return bytes(result)


def encode_deltas(data):
    """方式C: 相邻期差值. 第一期原始, 后续期=与前期差值.
    差值分布集中在0附近, 可能更可压缩."""
    result = bytearray()
    prev_reds = None
    prev_blue = None
    for row in data:
        reds = sorted(row[1:7])
        blue = row[7]
        if prev_reds is None:
            for r in reds:
                result.append(r)
            result.append(blue)
        else:
            for i in range(6):
                d = reds[i] - prev_reds[i]
                # [工程] 差值-32~32, 加上64偏移→0~64, 1字节
                result.append(d + 64)
            result.append(blue - prev_blue + 64)
        prev_reds = reds
        prev_blue = blue
    return bytes(result)


def encode_compact(data):
    """方式D: 紧凑编码. 每期映射为ID.
    C(33,6)种红球 × 16蓝球, ID范围 0~17,721,087.
    log2(17,721,088) ≈ 24.08 bits ≈ 4 bytes/期."""
    # 预计算红球组合→索引
    import itertools
    combo_index = {}
    for idx, c in enumerate(itertools.combinations(range(33), 6)):
        combo_index[c] = idx
    # [数学] C(33,6) = 1,107,568, 组合索引[0, 1107567]

    result = bytearray()
    for row in data:
        reds = tuple(sorted(n - 1 for n in row[1:7]))  # 0-indexed
        red_idx = combo_index[reds]
        blue_idx = row[7] - 1
        ticket_id = red_idx * 16 + blue_idx  # 0 ~ 17,721,087
        # 24位足够: 2^24 = 16,777,216 > 17,721,087? 不对!
        # 需要 log2(17,721,088)=24.08, 即25位>32位足够
        result.extend(struct.pack('>I', ticket_id))  # 4字节
    return bytes(result)


# ═══════════════════════════════════════════════════════════════════
# 压缩分析
# ═══════════════════════════════════════════════════════════════════

def compress_test(data_bytes, label, entropy_bits):
    """LZMA压缩测试. 返回压缩比和统计判定."""
    n_bits = len(data_bytes) * 8

    # LZMA 多级别压缩
    results = {}
    for level in [0, 3, 6, 9]:
        compressed = lzma.compress(data_bytes, preset=level)
        compressed_bits = len(compressed) * 8
        ratio = compressed_bits / n_bits
        results[f"level_{level}"] = {
            "raw_bytes": len(data_bytes),
            "compressed_bytes": len(compressed),
            "compression_ratio": round(ratio, 4),
            "bits_per_draw": round(compressed_bits / (len(data_bytes) / (entropy_bits / 8)), 2)
            if entropy_bits else 0,
        }

    # LZ77检验 (Ryabko 2024):
    # τ = n - |LZ(y)|, 拒绝H0(随机) if τ > n - log(1/α) - 1
    # α=0.01 → 阈值 ≈ n - 7.6
    best = min(results.values(), key=lambda x: x["compressed_bytes"])
    tau = n_bits - best["compressed_bytes"] * 8
    threshold = n_bits - int(math.log(1.0 / 0.01)) - 1  # n - log(100) - 1 ≈ n - 7.6
    reject_random = tau > threshold

    # 与理论熵比较
    below_entropy = best["compressed_bytes"] * 8 < entropy_bits

    return {
        "label": label,
        "raw_bytes": len(data_bytes),
        "raw_bits": n_bits,
        "theoretical_entropy_bits": entropy_bits,
        "lzma_levels": results,
        "best_compressed_bytes": best["compressed_bytes"],
        "best_ratio": best["compression_ratio"],
        "LZ77_tau": round(tau, 1),
        "LZ77_threshold": round(threshold, 1),
        "LZ77_reject_random": reject_random,
        "below_entropy_bound": below_entropy,
        "verdict": "NON-RANDOM — structure detected" if (reject_random or below_entropy)
                   else "RANDOM — no detectable structure",
    }


# ═══════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════

def run():
    data = load_data()
    n = len(data)
    # [数学] 每期熵: log2(C(33,6)×16) = log2(17,721,088) ≈ 24.078 bits
    entropy_per_draw = math.log2(math.comb(33, 6) * 16)
    total_entropy = entropy_per_draw * n

    print(f"=" * 60)
    print(f"实验1: LZMA通用压缩测试")
    print(f"=" * 60)
    print(f"数据: {n} 期")
    print(f"理论熵: {total_entropy:.0f} bits ({total_entropy/8:.0f} bytes)")
    print(f"  = {entropy_per_draw:.3f} bits/draw")
    print()

    encodings = [
        ("A: 位掩码(49bit/draw)", encode_bitmask(data), 49 * n),
        ("B: 位置序列", encode_positions(data), 7 * 8 * n),
        ("C: 相邻期差值", encode_deltas(data), 7 * 8 * n),
        ("D: 紧凑ID(32bit/draw)", encode_compact(data), 32 * n),
    ]

    results = []
    for label, data_bytes, raw_bits in encodings:
        # 判断理论熵是否适用此编码
        ent = total_entropy  # 全局熵
        r = compress_test(data_bytes, label, ent)
        results.append(r)
        print(f"  {label}:")
        print(f"    原始: {r['raw_bytes']} bytes → LZMA: {r['best_compressed_bytes']} bytes")
        print(f"    压缩率: {r['best_ratio']:.2%}, 熵界: {total_entropy/8:.0f} bytes")
        print(f"    LZ77 τ={r['LZ77_tau']:.0f}, 阈值={r['LZ77_threshold']:.0f}, 拒绝随机: {r['LZ77_reject_random']}")
        print(f"    判定: {r['verdict']}")
        print()

    # 综合结论
    any_structure = any(r["LZ77_reject_random"] or r["below_entropy_bound"] for r in results)
    print(f"{'─' * 60}")
    print(f"综合结论: ", end="")
    if any_structure:
        print("⚠️  序列存在可压缩结构 → 非纯随机 → 继续实验2+3")
    else:
        print("✅ 序列不可压缩 → 与真随机一致 → 时序预测方向可能不可行")
    print(f"{'─' * 60}")

    return {"results": results, "any_structure": any_structure}


if __name__ == "__main__":
    run()
