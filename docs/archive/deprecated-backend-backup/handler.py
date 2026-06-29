"""HTTP请求处理器 — 路由分发，委托各模块处理"""
import http.server
import json
import urllib.parse
from pathlib import Path

from server import db, fetcher, recommend
# ml_bridge 延迟导入 — 只在调用 ML 端点时加载, 避免启动时加载 XGB/LSTM

ROOT = Path(__file__).parent.parent
HTML_PATH = ROOT / "index.html"


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
        if self.path == "/":
            return self._html()

        if self.path == "/api/data":
            all_data = db.load_draws()
            short_data = all_data[-300:] if len(all_data) > 300 else all_data
            return self._json({
                "ok": True, "source": "本地数据库",
                "count": len(short_data), "total": len(all_data),
                "data": short_data,
            })

        if self.path.startswith("/api/fetch"):
            force = "force=1" in self.path or "force=true" in self.path
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

        if self.path == "/api/user-picks":
            picks = db.load_user_picks()
            return self._json({"ok": True, "picks": picks})

        if self.path == "/api/stats":
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

        if self.path == "/api/flush-cache":
            db.flush_cache()
            return self._json({"ok": True, "msg": "缓存标记已清除"})

        # 已注释: /api/strategy-weights — 策略已废弃

        # 已注释: 策略权重重算 — 策略已废弃
        # /api/strategy-weights/recalculate

        # 已注释: 回测历史+策略排名 — 策略已废弃
        # /api/backtest-history, /api/strategy-ranking

        # ===== 已注释: ML预测端点 — 全部对中一等奖无提升 =====
        # /api/ml/train, /api/ml/train/lstm
        # /api/ml/predict/xgb, /api/ml/predict/lstm, /api/ml/predict/ensemble
        # /api/ml/predict/copula~rmt, /api/ml/predict/advanced
        # /api/ml/status
        # /api/analysis/bias, /api/analysis/chaos
        # /api/hmm/status, /api/hmm/predict

        # 已注释: Sobol智能选号 — 依赖HMM (无预测力)
        # /api/sobol

        # 已注释: /api/negative — 负选择对个人彩民无实用价值

        # 已注释: /api/arbitrage — Mandel覆盖对个人彩民无实用价值

        # 已注释: 显著性检验 — 对选号无帮助
        # /api/experiment/significance

        if self.path.startswith("/api/evaluate/prizes"):
            all_data = db.load_draws()
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            n = int(params.get("n", ["3"])[0])
            tickets = self.ml_bridge.micro_3_tickets(n=n)
            if not tickets.get("tickets"):
                return self._json({"ok": False, "msg": "无法生成票集"})
            result = self.ml_bridge.evaluate_prizes(tickets["tickets"])
            result["tickets"] = tickets["tickets"]
            result["ok"] = True
            return self._json(result)

        # 已注释: OOT验证 — 无预测力
        # /api/ml/validate, /api/ml/validate/gpt

        # 保留: 覆盖设计 (Mandel — 数学有效)
        if self.path.startswith("/api/covering/generate"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            v = int(params.get("v", ["15"])[0])
            t = int(params.get("t", ["4"])[0])
            return self._json(self.ml_bridge.generate_covering(v=v, t=t))

        # 已注释: Sirius投资组合 — 依赖已废弃ML概率
        # /api/sirius/portfolio

        if self.path == "/api/rules/status":
            return self._json({"ok": True, **self.ml_bridge.get_rule_status()})

        # 保留: 微投资组合
        if self.path == "/api/micro/3tickets":
            return self._json(self.ml_bridge.micro_3_tickets(n=3))

        if self.path.startswith("/api/micro/tickets"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            n = int(params.get("n", ["3"])[0])
            soft = params.get("soft", ["0"])[0] in ("1", "true")
            luck_raw = params.get("luck", ["0"])[0]
            luck_mode = {'0': 'off', '1': 'blend', '2': 'pure'}.get(luck_raw, 'off')
            return self._json(self.ml_bridge.micro_3_tickets(n=n, soft=soft, luck_mode=luck_mode))

        # 已注释: Thompson/Lasso/GPT/自训练 — 无预测力
        # /api/thompson/*, /api/lasso/*, /api/ml/train/gpt
        # /api/ml/predict/gpt, /api/generate
        # /api/training/status, /api/training/best, /api/training/log

        # =========================

        if self.path == "/api/recommend":
            result = recommend.generate_recommendations()
            if result is None:
                return self._json({"ok": False, "msg": "数据不足"})
            return self._json({"ok": True, **result})

        if self.path == "/api/compare/ready":
            conn = db.get_db()
            ready = conn.execute("""
                SELECT DISTINCT up.period FROM user_picks up
                WHERE EXISTS (SELECT 1 FROM draws d WHERE d.period = up.period)
                ORDER BY up.period DESC LIMIT 20
            """).fetchall()
            conn.close()
            return self._json({"ok": True, "readyPeriods": [r[0] for r in ready]})

        if self.path.startswith("/api/prediction-log"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            stats_only = params.get("stats", ["0"])[0] in ("1", "true")
            if stats_only:
                return self._json({"ok": True, "stats": db.prediction_log_stats()})
            limit = int(params.get("limit", ["100"])[0])
            period = int(params["period"][0]) if params.get("period") else None
            entries = db.load_prediction_log(limit=limit, period=period)
            return self._json({"ok": True, "entries": entries})

        if self.path.startswith("/static/"):
            return self._serve_static()

        self.send_response(404)
        self.end_headers()

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
        if self.path == "/api/save":
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

        # 已注释: /api/strategy-picks — 策略已废弃

        # 已注释: 策略权重+回测 POST — 策略已废弃
        # /api/strategy-weights, /api/backtest-results, /api/strategy-picks
        # /api/ml/backtest-result, /api/ml/backtest/advanced

        if self.path == "/api/compare":
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

        # 已注释: ML回测 POST + 高级模型回测 GET — 无预测力
        # /api/ml/backtest-result, /api/ml/backtest/advanced

        if self.path == "/api/prediction-log":
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

        self.send_response(404)
        self.end_headers()

    def _parse_body(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            return json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return None
