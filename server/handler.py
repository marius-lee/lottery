"""HTTP请求处理器 — 路由分发，委托各模块处理"""
import http.server
import json
import urllib.parse
from pathlib import Path

from server import db, fetcher, recommend
# ml_bridge 延迟导入 — 只在调用 ML 端点时加载

ROOT = Path(__file__).parent.parent
HTML_PATH = ROOT / "index.html"


def _parse_query_int(path, key, default):
    """从 URL 查询字符串提取整数参数，缺省返回 default。"""
    parsed = urllib.parse.urlparse(path)
    params = urllib.parse.parse_qs(parsed.query)
    vals = params.get(key, [])
    return int(vals[0]) if vals else default


class Handler(http.server.BaseHTTPRequestHandler):
    _ml_bridge = None  # 惰性加载

    @property
    def ml_bridge(self):
        if Handler._ml_bridge is None:
            from server import ml_bridge
            Handler._ml_bridge = ml_bridge
        return Handler._ml_bridge

    def log_message(self, fmt, *args):
        pass

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(HTML_PATH.read_bytes())

    # ============ GET ============

    def do_GET(self):
        p = self.path

        if p == "/":
            return self._html()

        # ── 数据端点 ──
        if p == "/api/data":
            all_data = db.load_draws()
            short_data = all_data[-300:] if len(all_data) > 300 else all_data
            return self._json({
                "ok": True, "source": "本地数据库",
                "count": len(short_data), "total": len(all_data),
                "data": short_data,
            })

        if p.startswith("/api/fetch"):
            force = "force=1" in p or "force=true" in p
            source_name, short_data, new_count = fetcher.fetch_data(force=force)
            if short_data:
                resp = {
                    "ok": True, "source": source_name, "count": len(short_data),
                    "newCount": new_count, "data": short_data,
                }
                user_picks = db.load_user_picks()
                if user_picks:
                    resp["userPicks"] = user_picks
            else:
                resp = {"ok": False, "msg": "所有数据源均失败，请检查网络连接"}
            return self._json(resp)

        if p == "/api/user-picks":
            return self._json({"ok": True, "picks": db.load_user_picks()})

        if p == "/api/stats":
            return self._handle_stats()

        if p == "/api/flush-cache":
            db.flush_cache()
            return self._json({"ok": True, "msg": "缓存标记已清除"})

        if p == "/api/recommend":
            return self._handle_recommend()

        if p == "/api/rules/status":
            return self._json({"ok": True, **self.ml_bridge.get_rule_status()})

        # ── 微投资组合 ──
        if p.startswith("/api/micro/"):
            return self._handle_micro_get(p)

        # ── 覆盖设计 ──
        if p.startswith("/api/covering-diverse"):
            return self._handle_covering_diverse(p)

        if p.startswith("/api/covering/"):
            return self._handle_covering_get(p)

        # ── 奖项评估 ──
        if p.startswith("/api/evaluate/"):
            return self._handle_evaluate_get(p)

        # ── 对比 + 预测日志 ──
        if p.startswith("/api/compare/"):
            return self._handle_compare_get()
        if p.startswith("/api/prediction-log"):
            return self._handle_prediction_log_get(p)

        # ── 静态文件 ──
        if p.startswith("/static/"):
            return self._serve_static()

        self.send_response(404)
        self.end_headers()

    # ── 子路由: 微投资组合 ──

    def _handle_micro_get(self, path):
        if path == "/api/micro/3tickets":
            return self._json(self.ml_bridge.micro_3_tickets(n=3))
        n = _parse_query_int(path, "n", 3)
        soft = _parse_query_int(path, "soft", 0) in (1, None) and "soft=1" in path
        luck_raw = _parse_query_int(path, "luck", 0)
        luck_mode = {0: 'off', 1: 'blend', 2: 'pure'}.get(luck_raw, 'off')
        mo = _parse_query_int(path, "max_overlap", -1)
        max_overlap = None if mo < 0 else mo
        div_raw = _parse_query_int(path, "div", 0)
        diversity_mode = {0: None, 1: 'greedy'}.get(div_raw, None)
        five_period = _parse_query_int(path, "five_period", 0) == 1
        backtest_rank = _parse_query_int(path, "backtest", 0) == 1
        param_filter = _parse_query_int(path, "param", 0) == 1
        ba = _parse_query_int(path, "bundle_a", 0) or None
        bb = _parse_query_int(path, "bundle_b", 0) or None
        bundle_a = ba if ba and 1 <= ba <= 33 else None
        bundle_b = bb if bb and 1 <= bb <= 33 else None
        return self._json(self.ml_bridge.micro_3_tickets(
            n=n, soft=soft, luck_mode=luck_mode,
            max_overlap=max_overlap, diversity_mode=diversity_mode,
            five_period=five_period, backtest_rank=backtest_rank,
            param_filter=param_filter, bundle_a=bundle_a, bundle_b=bundle_b))

    # ── 子路由: 覆盖设计 ──

    def _handle_covering_get(self, path):
        v = _parse_query_int(path, "v", 15)
        t = _parse_query_int(path, "t", 4)
        return self._json(self.ml_bridge.generate_covering(v=v, t=t))

    def _handle_covering_diverse(self, path):
        v = _parse_query_int(path, "v", 15)
        t = _parse_query_int(path, "t", 4)
        n = _parse_query_int(path, "n", 6)
        mo = _parse_query_int(path, "max_overlap", -1)
        max_overlap = None if mo < 0 else mo
        return self._json(self.ml_bridge.generate_covering_diverse(
            v=v, t=t, n=n, max_overlap=max_overlap))

    # ── 子路由: 奖项评估 ──

    def _handle_evaluate_get(self, path):
        n = _parse_query_int(path, "n", 3)
        tickets = self.ml_bridge.micro_3_tickets(n=n)
        if not tickets.get("tickets"):
            return self._json({"ok": False, "msg": "无法生成票集"})
        result = self.ml_bridge.evaluate_prizes(tickets["tickets"])
        result["tickets"] = tickets["tickets"]
        result["ok"] = True
        return self._json(result)

    # ── 子路由: 对比 ──

    def _handle_compare_get(self):
        conn = db.get_db()
        ready = conn.execute("""
            SELECT DISTINCT up.period FROM user_picks up
            WHERE EXISTS (SELECT 1 FROM draws d WHERE d.period = up.period)
            ORDER BY up.period DESC LIMIT 20
        """).fetchall()
        conn.close()
        return self._json({"ok": True, "readyPeriods": [r[0] for r in ready]})

    # ── 子路由: 预测日志 ──

    def _handle_prediction_log_get(self, path):
        stats_only = _parse_query_int(path, "stats", 0) in (1, None) and "stats=1" in path
        if stats_only:
            return self._json({"ok": True, "stats": db.prediction_log_stats()})
        limit = _parse_query_int(path, "limit", 100)
        period = _parse_query_int(path, "period", 0) or None
        entries = db.load_prediction_log(limit=limit, period=period)
        return self._json({"ok": True, "entries": entries})

    # ── 子路由: 统计 ──

    def _handle_stats(self):
        conn = db.get_db()
        draw_count = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        pick_count = conn.execute("SELECT COUNT(*) FROM user_picks").fetchone()[0]
        hit_stats = []
        for row in conn.execute("""
            SELECT up.period, up.r1, up.r2, up.r3, up.r4, up.r5, up.r6, up.blue,
                   up.strategy, up.score, up.created_at
            FROM user_picks up ORDER BY up.period
        """):
            up = dict(row)
            draw = conn.execute(
                "SELECT r1,r2,r3,r4,r5,r6,blue FROM draws WHERE period=?", (up["period"],)
            ).fetchone()
            if draw:
                draw_reds = {draw[0], draw[1], draw[2], draw[3], draw[4], draw[5]}
                user_reds = {up["r1"], up["r2"], up["r3"], up["r4"], up["r5"], up["r6"]}
                red_hits = len(draw_reds & user_reds)
                blue_hit = 1 if up["blue"] == draw[6] else 0
                hit_stats.append({
                    "period": up["period"], "red_hits": red_hits,
                    "blue_hit": blue_hit, "strategy": up["strategy"],
                })
        conn.close()
        return self._json({
            "ok": True, "drawCount": draw_count, "pickCount": pick_count,
            "hitStats": hit_stats[-50:],
        })

    # ── 子路由: 推荐 ──

    def _handle_recommend(self):
        result = recommend.generate_recommendations()
        if result is None:
            return self._json({"ok": False, "msg": "数据不足"})
        return self._json({"ok": True, **result})

    # ============ Static files ============

    def _serve_static(self):
        """Serve static files (CSS, JS) from the static/ directory."""
        file_path = ROOT / self.path.lstrip("/")
        if not file_path.resolve().is_relative_to(ROOT.resolve()):
            self.send_response(403)
            self.end_headers()
            return
        if not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        content_type = "text/css" if file_path.suffix == ".css" else "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    # ============ POST ============

    def do_POST(self):
        p = self.path

        if p == "/api/save":
            return self._handle_save_post()

        if p == "/api/compare":
            return self._handle_compare_post()

        if p == "/api/prediction-log":
            return self._handle_prediction_log_post()

        self.send_response(404)
        self.end_headers()

    # ── 子路由: 保存 ──

    def _handle_save_post(self):
        payload = self._parse_body()
        if not payload:
            return
        picks = payload.get("picks", [])
        for p in picks:
            db.insert_user_pick(
                period=p["period"], reds=p["reds"], blue=p["blue"],
                strategy=p.get("strategy", ""), score=p.get("score", 0),
            )
        return self._json({"ok": True, "saved": len(picks)})

    # ── 子路由: 对比 ──

    def _handle_compare_post(self):
        payload = self._parse_body()
        if not payload:
            return
        period = int(payload["period"])
        actual_reds = set(int(x) for x in payload["reds"])
        actual_blue = int(payload["blue"])

        conn = db.get_db()
        existing = conn.execute("SELECT 1 FROM draws WHERE period=?", (period,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO draws (period, r1, r2, r3, r4, r5, r6, blue, source) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [period] + sorted(actual_reds) + [actual_blue, "用户录入"],
            )
            conn.commit()

        user_picks = conn.execute(
            "SELECT id, r1, r2, r3, r4, r5, r6, blue, strategy, score FROM user_picks WHERE period=?",
            (period,),
        ).fetchall()

        pick_results = []
        strategy_hits = {}

        for p in user_picks:
            user_reds = {p[1], p[2], p[3], p[4], p[5], p[6]}
            rh = len(user_reds & actual_reds)
            bh = 1 if p[7] == actual_blue else 0
            strat = p[8] or "unknown"
            pick_results.append({
                "reds": sorted(user_reds), "blue": p[7],
                "strategy": strat, "red_hits": rh, "blue_hit": bh,
            })
            if strat not in strategy_hits:
                strategy_hits[strat] = {"hits": 0, "tries": 0, "red_hits_sum": 0, "blue_hits": 0}
            strategy_hits[strat]["tries"] += 1
            strategy_hits[strat]["red_hits_sum"] += rh
            strategy_hits[strat]["blue_hits"] += bh
            if rh >= 3 or bh == 1:
                strategy_hits[strat]["hits"] += 1

        strat_picks = conn.execute(
            "SELECT r1, r2, r3, r4, r5, r6, blue, strategy FROM strategy_picks WHERE period=?",
            (period,),
        ).fetchall()
        for sp in strat_picks:
            sp_reds = {sp[0], sp[1], sp[2], sp[3], sp[4], sp[5]}
            sp_rh = len(sp_reds & actual_reds)
            sp_bh = 1 if sp[6] == actual_blue else 0
            sp_strat = sp[7]
            pick_results.append({
                "reds": sorted(sp_reds), "blue": sp[6],
                "strategy": sp_strat, "red_hits": sp_rh, "blue_hit": sp_bh,
                "source": "strategy",
            })
            if sp_strat not in strategy_hits:
                strategy_hits[sp_strat] = {"hits": 0, "tries": 0, "red_hits_sum": 0, "blue_hits": 0}
            strategy_hits[sp_strat]["tries"] += 1
            strategy_hits[sp_strat]["red_hits_sum"] += sp_rh
            strategy_hits[sp_strat]["blue_hits"] += sp_bh
            if sp_rh >= 3 or sp_bh == 1:
                strategy_hits[sp_strat]["hits"] += 1

        weight_adjustments = {}
        for strat, stats in strategy_hits.items():
            avg_red = stats["red_hits_sum"] / stats["tries"]
            score = (avg_red / 1.09) * 0.7 + (stats["blue_hits"] / stats["tries"] / 0.0625) * 0.3
            weight_adjustments[strat] = round(max(0.3, min(2.0, score)), 2)

        existing_w = {}
        for row in conn.execute("SELECT name, weight FROM strategy_weights").fetchall():
            existing_w[row[0]] = row[1]

        for strat, new_w in weight_adjustments.items():
            old_w = existing_w.get(strat, 1.0)
            blended = round(old_w * 0.7 + new_w * 0.3, 2)
            conn.execute(
                "INSERT OR REPLACE INTO strategy_weights (name, weight, hits, tries, updated_at) "
                "VALUES (?, ?, ?, ?, datetime('now','localtime'))",
                (strat, blended, strategy_hits[strat]["hits"], strategy_hits[strat]["tries"]),
            )
        conn.commit()

        for p in pick_results:
            conn.execute(
                "INSERT OR IGNORE INTO prediction_log (period, source, reds_json, blue, actual_reds_json, actual_blue, red_hits, blue_hit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (period, p.get("strategy", "unknown"),
                 json.dumps(p.get("reds", [])), p.get("blue", 0),
                 json.dumps(sorted(actual_reds)), actual_blue,
                 p.get("red_hits", 0), p.get("blue_hit", 0)),
            )
        conn.commit()
        conn.close()

        # v4: 写入 strategy_performance_log 并触发权重重算
        from server import weight_optimizer
        db.init_performance_log()
        for strat, stats in strategy_hits.items():
            if stats["tries"] > 0:
                db.insert_performance_log(
                    period, strat,
                    stats["red_hits_sum"],
                    stats["blue_hits"],
                )
        new_count = db.count_performance_log_since(period - 10)
        recalculated = None
        if new_count >= 5:
            rw, bw = weight_optimizer.compute_all_weights()
            db.save_strategy_weights(rw, {k: {"hits": 0, "tries": 0} for k in rw})
            recalculated = {"red": rw, "blue": bw}

        resp = {
            "ok": True, "period": period, "pickCount": len(pick_results),
            "picks": pick_results, "strategyPerformance": strategy_hits,
            "weightAdjustments": weight_adjustments,
        }
        if recalculated:
            resp["recalculatedWeights"] = recalculated
        return self._json(resp)

    # ── 子路由: 预测日志 POST ──

    def _handle_prediction_log_post(self):
        payload = self._parse_body()
        if not payload:
            return
        if "entries" in payload:
            db.save_prediction_log(payload["entries"])
            return self._json({"ok": True, "saved": len(payload["entries"])})
        if "period" in payload and "actual_reds" in payload:
            db.update_prediction_log_actual(
                int(payload["period"]), payload["actual_reds"], int(payload["actual_blue"]),
            )
            return self._json({"ok": True, "msg": "已更新"})
        return self._json({"ok": False, "msg": "无效请求"})

    # ============ Helpers ============

    def _parse_body(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            return json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return None