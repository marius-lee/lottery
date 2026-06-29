"""自动兑奖引擎 — 数据拉取后自动匹配预测与实际开奖，闭环驱动权重更新.

每次 fetch 新数据后调用 auto_claim_all():
  1. 扫描所有 user_picks 和 prediction_log，找出未兑奖的条目
  2. 匹配 draws 表同期开奖数据，计算红球命中/蓝球命中
  3. 更新 prediction_log.actual_* / red_hits / blue_hit
  4. 写入 strategy_performance_log
  5. 累计 ≥5 期新数据时触发权重重算

用法:
  from server.auto_claim import auto_claim_all
  stats = auto_claim_all()
  print(f"已兑奖 {stats['claimed']} 注, 新期数 {stats['new_periods']}")
"""
from server import db


def auto_claim_all():
    """全量自动兑奖 — 扫描所有未兑奖记录并匹配开奖数据.

    Returns:
        dict with claimed, new_periods, errors
    """
    conn = db.get_db()

    # 1. 查找所有已有开奖数据的期号
    draw_periods = set(r[0] for r in conn.execute(
        "SELECT period FROM draws ORDER BY period").fetchall())

    # 2. 查找所有 user_picks 中对应期号有开奖数据的
    picks = conn.execute("""
        SELECT up.id, up.period, up.r1, up.r2, up.r3, up.r4, up.r5, up.r6, up.blue,
               up.strategy, up.score
        FROM user_picks up
        WHERE up.period IN (SELECT period FROM draws)
        ORDER BY up.period DESC
    """).fetchall()

    # 3. 查找已兑奖的 prediction_log entry (避免重复兑奖)
    claimed_ids = set(r[0] for r in conn.execute(
        "SELECT id FROM prediction_log WHERE actual_reds_json IS NOT NULL").fetchall()
        if r[0] is not None)

    # 同时检查 prediction_log 是否已有对应 (period, source) 的记录
    existing_logs = set()
    for row in conn.execute(
        "SELECT period, reds_json, blue FROM prediction_log WHERE actual_reds_json IS NOT NULL"
    ).fetchall():
        existing_logs.add((row[0], row[1], row[2]))

    claimed = 0
    new_periods = set()
    errors = []

    for p in picks:
        pid = p[0]
        period = p[1]
        reds_raw = [p[2], p[3], p[4], p[5], p[6], p[7]]
        blue = p[8]
        strategy = p[9] or "unknown"

        # 查找同期的实际开奖
        draw = conn.execute(
            "SELECT r1, r2, r3, r4, r5, r6, blue FROM draws WHERE period=?",
            (period,)
        ).fetchone()
        if not draw:
            continue

        user_reds = set(reds_raw)
        draw_reds = {draw[0], draw[1], draw[2], draw[3], draw[4], draw[5]}
        red_hits = len(user_reds & draw_reds)
        blue_hit = 1 if blue == draw[6] else 0

        reds_json = ",".join(str(x) for x in sorted(reds_raw))
        actual_reds_json = ",".join(str(x) for x in sorted(draw_reds))

        # 检查是否已有该来源该期号的记录
        log_key = (period, reds_json, blue)
        if log_key in existing_logs:
            continue

        # 写入/更新 prediction_log
        existing = conn.execute(
            "SELECT id FROM prediction_log WHERE period=? AND reds_json=? AND blue=? AND actual_reds_json IS NULL",
            (period, reds_json, blue)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE prediction_log SET actual_reds_json=?, actual_blue=?, red_hits=?, blue_hit=? WHERE id=?",
                (actual_reds_json, draw[6], red_hits, blue_hit, existing[0])
            )
        else:
            # 插入新记录（如果之前没写 prediction_log）
            conn.execute(
                "INSERT INTO prediction_log (period, source, reds_json, blue, "
                "actual_reds_json, actual_blue, red_hits, blue_hit, "
                "pred_r1, pred_r2, pred_r3, pred_r4, pred_r5, pred_r6) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (period, strategy, reds_json, blue,
                 actual_reds_json, draw[6], red_hits, blue_hit,
                 reds_raw[0], reds_raw[1], reds_raw[2],
                 reds_raw[3], reds_raw[4], reds_raw[5])
            )

        # 写入 strategy_performance_log
        conn.execute(
            "INSERT INTO strategy_performance_log (period, strategy, red_hits, blue_hit) "
            "VALUES (?, ?, ?, ?)",
            (period, strategy, red_hits, blue_hit)
        )

        claimed += 1
        new_periods.add(period)
        existing_logs.add(log_key)

    conn.commit()

    # 4. 统计 strategy_picks 中未兑奖的
    sp = conn.execute("""
        SELECT sp.id, sp.period, sp.r1, sp.r2, sp.r3, sp.r4, sp.r5, sp.r6, sp.blue, sp.strategy
        FROM strategy_picks sp
        WHERE sp.period IN (SELECT period FROM draws)
        ORDER BY sp.period DESC
    """).fetchall()

    for s in sp:
        period = s[1]
        reds_raw = [s[2], s[3], s[4], s[5], s[6], s[7]]
        blue = s[8]
        strategy = s[9] or "unknown"

        draw = conn.execute(
            "SELECT r1, r2, r3, r4, r5, r6, blue FROM draws WHERE period=?",
            (period,)
        ).fetchone()
        if not draw:
            continue

        user_reds = set(reds_raw)
        draw_reds = {draw[0], draw[1], draw[2], draw[3], draw[4], draw[5]}
        red_hits = len(user_reds & draw_reds)
        blue_hit = 1 if blue == draw[6] else 0
        reds_json = ",".join(str(x) for x in sorted(reds_raw))
        actual_reds_json = ",".join(str(x) for x in sorted(draw_reds))

        log_key = (period, reds_json, blue)
        if log_key in existing_logs:
            continue

        existing = conn.execute(
            "SELECT id FROM prediction_log WHERE period=? AND reds_json=? AND blue=? AND actual_reds_json IS NULL",
            (period, reds_json, blue)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE prediction_log SET actual_reds_json=?, actual_blue=?, red_hits=?, blue_hit=? WHERE id=?",
                (actual_reds_json, draw[6], red_hits, blue_hit, existing[0])
            )
        else:
            conn.execute(
                "INSERT INTO prediction_log (period, source, reds_json, blue, "
                "actual_reds_json, actual_blue, red_hits, blue_hit, "
                "pred_r1, pred_r2, pred_r3, pred_r4, pred_r5, pred_r6) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (period, strategy, reds_json, blue,
                 actual_reds_json, draw[6], red_hits, blue_hit,
                 reds_raw[0], reds_raw[1], reds_raw[2],
                 reds_raw[3], reds_raw[4], reds_raw[5])
            )

        conn.execute(
            "INSERT INTO strategy_performance_log (period, strategy, red_hits, blue_hit) "
            "VALUES (?, ?, ?, ?)",
            (period, strategy, red_hits, blue_hit)
        )

        claimed += 1
        new_periods.add(period)
        existing_logs.add(log_key)

    conn.commit()

    # 3b. 直接兑奖 prediction_log (由 _log_prediction 写入, 无对应 user_picks)
    unclaimed_preds = conn.execute("""
        SELECT id, period, source, reds_json, blue
        FROM prediction_log
        WHERE actual_reds_json IS NULL AND period IN (SELECT period FROM draws)
        ORDER BY period DESC
    """).fetchall()

    for pred in unclaimed_preds:
        pid, period, source, reds_json, blue = pred
        reds = [int(x.strip()) for x in reds_json.split(",") if x.strip().isdigit()]
        if len(reds) != 6:
            continue

        draw = conn.execute(
            "SELECT r1, r2, r3, r4, r5, r6, blue FROM draws WHERE period=?",
            (period,)
        ).fetchone()
        if not draw:
            continue

        user_reds = set(reds)
        draw_reds = {draw[0], draw[1], draw[2], draw[3], draw[4], draw[5]}
        red_hits = len(user_reds & draw_reds)
        blue_hit = 1 if blue == draw[6] else 0
        actual_reds_json = ",".join(str(x) for x in sorted(draw_reds))

        log_key = (period, reds_json, blue)
        if log_key in existing_logs:
            continue

        conn.execute(
            "UPDATE prediction_log SET actual_reds_json=?, actual_blue=?, red_hits=?, blue_hit=? WHERE id=?",
            (actual_reds_json, draw[6], red_hits, blue_hit, pid)
        )

        conn.execute(
            "INSERT INTO strategy_performance_log (period, strategy, red_hits, blue_hit) "
            "VALUES (?, ?, ?, ?)",
            (period, source or "unknown", red_hits, blue_hit)
        )

        claimed += 1
        new_periods.add(period)
        existing_logs.add(log_key)

    conn.commit()

    # 5. 累计 ≥5 条新性能数据触发权重重算 (与 handler.py _handle_compare_post 对齐)
    recalculated = None
    if new_periods:
        min_period = min(new_periods)
        new_count = db.count_performance_log_since(min_period - 1)
        if new_count >= 5:
            try:
                from server import weight_optimizer
                rw, bw = weight_optimizer.compute_all_weights()
                db.save_strategy_weights(rw, {k: {"hits": 0, "tries": 0} for k in rw})
                recalculated = {"red": {k: round(v, 3) for k, v in rw.items()},
                                "blue": {k: round(v, 3) for k, v in bw.items()}}
            except Exception as e:
                errors.append(f"weight_recalc: {e}")

    conn.close()

    return {
        "claimed": claimed,
        "new_periods": sorted(new_periods),
        "total_new_periods": len(new_periods),
        "recalculated": recalculated,
        "errors": errors,
    }


def get_claims_summary():
    """获取兑奖总览统计.

    Returns:
        dict with total_claimed, total_unclaimed, hit_distribution, strategy_hits
    """
    conn = db.get_db()

    total_claimed = conn.execute(
        "SELECT COUNT(*) FROM prediction_log WHERE actual_reds_json IS NOT NULL"
    ).fetchone()[0]

    total_unclaimed = conn.execute(
        "SELECT COUNT(*) FROM prediction_log WHERE actual_reds_json IS NULL"
    ).fetchone()[0]

    # 命中分布
    hit_dist = {}
    for row in conn.execute(
        "SELECT red_hits, blue_hit, COUNT(*) as cnt FROM prediction_log "
        "WHERE actual_reds_json IS NOT NULL "
        "GROUP BY red_hits, blue_hit"
    ).fetchall():
        key = f"{row[0]}R{'+B' if row[1] else ''}"
        hit_dist[key] = row[2]

    # 策略级命中
    strategy_stats = []
    for row in conn.execute("""
        SELECT source as strategy,
               COUNT(*) as total,
               AVG(red_hits) as avg_red,
               SUM(CASE WHEN blue_hit=1 THEN 1 ELSE 0 END)*1.0/COUNT(*) as blue_rate,
               SUM(CASE WHEN red_hits>=3 OR blue_hit=1 THEN 1 ELSE 0 END) as wins
        FROM prediction_log
        WHERE actual_reds_json IS NOT NULL
        GROUP BY source
        ORDER BY total DESC
        LIMIT 20
    """).fetchall():
        strategy_stats.append({
            "strategy": row[0],
            "total": row[1],
            "avg_red": round(row[2], 2),
            "blue_rate": round(row[3], 3),
            "wins": row[4],
        })

    conn.close()
    return {
        "total_claimed": total_claimed,
        "total_unclaimed": total_unclaimed,
        "hit_distribution": hit_dist,
        "strategy_stats": strategy_stats,
    }
