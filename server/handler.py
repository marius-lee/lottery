"""HTTP请求处理器 — 路由分发，委托各模块处理"""
import http.server
import json
import urllib.parse
from pathlib import Path

from server.query_parser import qbool, qint, qlist, qstr, qfloat
from server import db, fetcher, recommend

ROOT = Path(__file__).parent.parent
HTML_PATH = ROOT / "index.html"


def _parse_query(path):
    """Parse URL query string into a flat dict (first value only)."""
    qs = urllib.parse.urlparse(path).query
    result = {}
    for k, v in urllib.parse.parse_qs(qs).items():
        result[k] = v[0] if v else ''
    return result


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

    _ROUTES = {
        "/api/micro/": "_handle_micro_get",
        "/api/zhang/": "_handle_zhang_get",
        "/api/peng/": "_handle_peng_get",
        "/api/wuming/": "_handle_wuming_get",
        "/api/jiangjialin/": "_handle_jiangjialin_get",
        "/api/lizhilin/": "_handle_lizhilin_get",
        "/api/covering/": "_handle_covering_get",
        "/api/covering-diverse": "_handle_covering_diverse",
        "/api/evaluate/": "_handle_evaluate_get",
        "/api/compare/": "_handle_compare_get",
        "/api/prediction-log": "_handle_prediction_log_get",
        "/api/blue/": "_handle_blue_get",
        "/api/red/": "_handle_red_get",
        "/api/weier/": "_handle_weier_get",
        "/api/lixiangchun/": "_handle_lixiangchun_get",
        "/api/liudajun/": "_handle_liudajun_get",
        "/api/zeng/": "_handle_zeng_get",
        "/static/": "_serve_static",
    }

    def do_GET(self):
        p = self.path
        if p == "/":
            return self._html()

        clean_path = p.split("?")[0]
        q = _parse_query(p)

        # Exact-match endpoints
        handlers = {
            "/api/data": lambda: self._json({"ok": True, "source": "本地数据库",
                "count": min(len(db.load_draws()), 300), "total": len(db.load_draws()),
                "data": db.load_draws()[-300:]}),
            "/api/fetch": lambda: self._json(self._handle_fetch(p)),
            "/api/user-picks": lambda: self._json({"ok": True, "picks": db.load_user_picks()}),
            "/api/stats": self._handle_stats,
            "/api/flush-cache": lambda: self._json({"ok": True, "msg": "缓存标记已清除"}),
            "/api/recommend": self._handle_recommend,
            "/api/rules/status": lambda: self._json({"ok": True, **self.ml_bridge.get_rule_status()}),
            "/api/zone-break/data": lambda: self._json(self.ml_bridge.get_zone_break_data()),
            "/api/weier/conditions": lambda: self._json(self.ml_bridge.get_weier_conditions()),
            "/api/backtest/run": lambda: self._json(self.ml_bridge.run_backtest()),
            "/api/backtest/results": lambda: self._json({
                "ok": True, "results": self.ml_bridge.get_backtest_results()}),
            "/api/backtest/weights": lambda: self._json(
                self.ml_bridge.get_strategy_weights()),
            "/api/integration/status": lambda: self._json(self.ml_bridge.integration_status_api()),
            "/api/bias/draw": lambda: self._json(self.ml_bridge.bias_draw(n=qint(q, "n", 3))),
            "/api/bias/status": lambda: self._json(self.ml_bridge.bias_status_api()),
            "/api/bl/draw": lambda: self._json(self.ml_bridge.bl_draw(n=qint(q, "n", 3))),
            "/api/position/draw": lambda: self._json(self.ml_bridge.position_draw(n=qint(q, "n", 3))),
"/api/ensemble/draw": lambda: self._json(self.ml_bridge.ensemble_draw(
                n=qint(q, "n", 3), method=qstr(q, "method", "ensemble"),
                fdr=qbool(q, "fdr", True))),
            "/api/monitor": lambda: self._json(self.ml_bridge.monitor_api(
                tickets=qint(q, "n", 3), pool_v=qint(q, "v", 15),
                pool_blue=qint(q, "blue", 6), capital=qint(q, "cap", 5000))),
            "/api/advanced/generate": lambda: self._json(
                self.ml_bridge.advanced_generate(n=qint(q, "n", 3))),
            "/api/claims/summary": lambda: self._json(self.ml_bridge.claims_summary_api()),
            "/api/claims/run": lambda: self._json(self.ml_bridge.claims_run_api()),
            "/api/mandel/config": lambda: self._json(self.ml_bridge.mandel_config_api()),
            "/api/mandel/preview": lambda: self._json(self.ml_bridge.mandel_preview_api(
                v=qint(q, "v", 12))),
            "/api/mandel/jackpot": lambda: self._json(self.ml_bridge.mandel_jackpot_api()),
            "/api/schedule/status": lambda: self._json(self.ml_bridge.schedule_status_api()),
            "/api/wheeling/compare": lambda: self._json(self.ml_bridge.wheel_comparison_api()),
            "/api/wheeling/generate": lambda: self._json(self.ml_bridge.wheeling_generate_api(
                v=qint(q, "v", 10))),
            "/api/kelly": lambda: self._json(self.ml_bridge.kelly_api(
                tickets=qint(q, "n", 3), pool_v=qint(q, "v", 15),
                coverage_pct=float(q.get("cov", 36)), blue_pct=float(q.get("blue", 37.5)))),
            "/api/sprt/monitor": lambda: self._json(self.ml_bridge.sprt_monitor_api()),
            "/api/nist/test": lambda: self._json(self.ml_bridge.nist_api()),
            "/api/exact-cover/solve": lambda: self._json(self.ml_bridge.exact_cover_api(
                v=qint(q, "v", 15), t=qint(q, "t", 4), n=qint(q, "n", 3))),
            "/api/exact-cover/compare": lambda: self._json(self.ml_bridge.exact_cover_compare_api(
                n=qint(q, "n", 3))),
            "/api/cond-entropy/analyze": lambda: self._json(self.ml_bridge.cond_entropy_api()),
            "/api/cond-entropy/blue": lambda: self._json(self.ml_bridge.cond_entropy_blue_api(
                n=qint(q, "n", 6))),
            "/api/diffset/table": lambda: self._json(self.ml_bridge.diffset_table_api()),
            "/api/multi-period/stats": lambda: self._json(self.ml_bridge.multi_period_stats_api(t=qint(q, "t", 4))),
            "/api/multi-period/clear": lambda: self._json(self.ml_bridge.multi_period_clear_api(t=qint(q, "t", 4))),
            "/api/bandit/select": lambda: self._json(self.ml_bridge.bandit_select_api(
                n=qint(q, "n", 3))),
            "/api/bandit/feedback": lambda: self._json(self.ml_bridge.bandit_feedback_api(
                score=qfloat(q, "score", 0), arm_id=qstr(q, "arm_id", ""))),
            "/api/bandit/summary": lambda: self._json(self.ml_bridge.bandit_summary_api()),
            "/api/fdr/filter": lambda: self._json(self.ml_bridge.fdr_filter_api()),
            "/api/changepoint/detect": lambda: self._json(self.ml_bridge.changepoint_api()),
            "/api/mi/analyze": lambda: self._json(self.ml_bridge.mi_selector_api()),
            "/api/zeng/dashboard": lambda: self._json(self.ml_bridge.zeng_dashboard()),
            "/api/zeng/generate": lambda: self._json(self.ml_bridge.zeng_generate(
                n=qint(q, "n", 3), odd=qint(q, "odd", 3), big=qint(q, "big", 3))),

        }
        if clean_path in handlers:
            return handlers[clean_path]()

        # Prefix-match routes
        for prefix, handler_name in self._ROUTES.items():
            if p.startswith(prefix):
                handler = getattr(self, handler_name)
                return handler(p) if handler_name.startswith("_handle_") else handler()

        self._json({"ok": False, "msg": "404 Not Found"}, code=404)
        return

    # ── 子路由 ──

    def _handle_fetch(self, path):
        q = _parse_query(path)
        force = qbool(q, "force")
        source_name, short_data, new_count = fetcher.fetch_data(force=force)
        claim_stats = None
        if short_data:
            # 自动兑奖: 新数据后匹配所有未兑奖预测
            try:
                from server.auto_claim import auto_claim_all
                claim_stats = auto_claim_all()
            except Exception:
                pass
            resp = {"ok": True, "source": source_name, "count": len(short_data),
                    "newCount": new_count, "data": short_data}
            if claim_stats:
                resp["autoClaim"] = claim_stats
            picks = db.load_user_picks()
            if picks: resp["userPicks"] = picks
        else:
            resp = {"ok": False, "msg": "所有数据源均失败"}
        return resp

    def _handle_wuming_get(self, path):
        clean = path.split("?")[0]
        dispatch = {
            "/api/wuming/blue-alert": self.ml_bridge.wuming_blue_extreme_alert,
            "/api/wuming/oscillation": self.ml_bridge.wuming_cyclic_oscillation,
            "/api/wuming/period5": self.ml_bridge.wuming_period5,
            "/api/wuming/cold9": self.ml_bridge.wuming_cold9,
            "/api/wuming/zone6": self.ml_bridge.wuming_zone6,
            "/api/wuming/positions": self.ml_bridge.wuming_position_filter,
            "/api/wuming/repeats": self.ml_bridge.wuming_repeat_analysis,
            "/api/wuming/extreme-dan": self.ml_bridge.wuming_extreme_dan,
            "/api/wuming/sum-compound": self.ml_bridge.wuming_sum_compound,
            "/api/wuming/sub4-add4": self.ml_bridge.xia_sub4_add4_blue,
            "/api/wuming/compute-reds": self.ml_bridge.xia_compute_reds,
        }
        fn = dispatch.get(clean)
        return self._json(fn() if fn else {"ok": False, "msg": "未知端点"})

    def _handle_jiangjialin_get(self, path):
        q = _parse_query(path)
        return self._json(self.ml_bridge.generate_jiang_jialin(
            n=qint(q, "n", 3),
            use_gap=qbool(q, "gap", True),
            use_span=qbool(q, "span", True),
            use_pattern=qbool(q, "pattern", True),
            use_shrink=qbool(q, "shrink", True),
            blue_mode=qstr(q, "blue", "mod3")))

    def _handle_lizhilin_get(self, path):
        q = _parse_query(path)
        kwargs = {k: qint(q, k, 1) for k in ["dan8","dan3","trans","kill","btail"]}
        kwargs.update(bten=qint(q, "bten", 0), bperiod=qint(q, "bperiod", 0))
        return self._json(self.ml_bridge.generate_li_zhilin(n=qint(q, "n", 3), **kwargs))

    def _handle_weier_get(self, path):
        return self._json(self.ml_bridge.generate_weier())

    def _handle_liudajun_get(self, path):
        clean = path.split("?")[0]
        if clean == "/api/liudajun/position-tails":
            return self._json(self.ml_bridge.liudajun_position_tails(
                window=qint(_parse_query(path), "window", 50)))
        return self._json({"ok": False, "msg": "unknown endpoint"})


    def _handle_zeng_get(self, path):
        clean = path.split("?")[0]
        q = _parse_query(path)
        dispatch = {
            "/api/zeng/dashboard": lambda: self.ml_bridge.zeng_dashboard(),
            "/api/zeng/generate": lambda: self.ml_bridge.zeng_generate(
                n=qint(q, "n", 3), odd=qint(q, "odd", 3), big=qint(q, "big", 3)),
        }
        fn = dispatch.get(clean)
        return self._json(fn() if fn else {"ok": False, "msg": "未知端点"})
    def _handle_lixiangchun_get(self, path):
        clean = path.split("?")[0]
        q = _parse_query(path)
        dispatch = {
            "/api/lixiangchun/dashboard": lambda: self.ml_bridge.lixiangchun_dashboard(),
            "/api/lixiangchun/spread": lambda: self.ml_bridge.lixiangchun_spread(qlist(q, "numbers")),
            "/api/lixiangchun/skewness": lambda: self.ml_bridge.lixiangchun_skewness(qlist(q, "current"), qlist(q, "previous")),
            "/api/lixiangchun/ac": lambda: self.ml_bridge.lixiangchun_ac_value(qlist(q, "numbers")),
            "/api/lixiangchun/sanlang": lambda: self.ml_bridge.lixiangchun_sanlang(),
            "/api/lixiangchun/dhr": lambda: self.ml_bridge.lixiangchun_dhr(qint(q, "num", 1)),
            "/api/lixiangchun/trend-score": lambda: self.ml_bridge.lixiangchun_trend_score(qlist(q, "reds"), qint(q, "blue", None)),
            "/api/lixiangchun/generate": lambda: self.ml_bridge.lixiangchun_generate(qint(q, "n", 3)),
        }
        fn = dispatch.get(clean)
        return self._json(fn() if fn else {"ok": False, "msg": "unknown endpoint"})

    # ── 子路由: 微投资组合 ──

    def _handle_micro_get(self, path):
        if path == "/api/micro/3tickets":
            return self._json(self.ml_bridge.micro_3_tickets(n=3))
        q = _parse_query(path)
        n = qint(q, "n", 3)
        soft = qbool(q, "adv_filter") or qbool(q, "soft")
        five_period = qbool(q, "five_period")
        pattern_rules = qbool(q, "pattern_rules")
        luck_mode = {0: 'off', 2: 'pure'}.get(qint(q, "luck"), 'off')
        mo = qint(q, "max_overlap", -1)
        max_overlap = None if mo < 0 else mo
        diversity_mode = {0: None, 1: 'greedy'}.get(qint(q, "div"), None)
        author_mode = q.get("author", None)
        return self._json(self.ml_bridge.micro_3_tickets(
            n=n, soft=soft, luck_mode=luck_mode,
            max_overlap=max_overlap, diversity_mode=diversity_mode,
            five_period=five_period, backtest_rank=qbool(q, "backtest"),
            pattern_rules=pattern_rules,
            author_mode=author_mode,
            use_freq_blue=qbool(q, 'freq_blue'), blue_mode=qstr(q, 'blue_mode', 'freq'),
            red_mode=qstr(q, 'red_mode', 'pool'),
            strategy_mode=qstr(q, 'strategy', None),
            v_override=qint(q, 'v_override', None), t=qint(q, 't', 4), multi_period=qbool(q, 'multi_period')))
    def _handle_zhang_get(self, path):
        clean = path.split("?")[0]
        q = _parse_query(path)
        n = qint(q, "n", 3)
        dan = qlist(q, "dan") or None
        dispatch = {
            "/api/zhang/twelve-value": lambda: self.ml_bridge.generate_twelve_value(n=n, dan=dan),
            "/api/zhang/eight-value": lambda: self.ml_bridge.generate_eight_value(n=n),
            "/api/zhang/combined": lambda: self.ml_bridge.generate_zhang_combined(n=n, dan=dan),
            "/api/zhang/grid": lambda: self.ml_bridge.generate_grid_selection(n=n),
            "/api/zhang/dan1": lambda: self.ml_bridge.generate_dan1(),
            "/api/zhang/dan2": lambda: self.ml_bridge.generate_dan2(),
        }
        fn = dispatch.get(clean)
        return self._json(fn() if fn else {"ok": False, "msg": "未知端点"})

    # ── 子路由: 彭浩算法 ──

    def _handle_peng_get(self, path):
        clean = path.split("?")[0]
        q = _parse_query(path)
        dispatch = {
            "/api/peng/channel": lambda: self.ml_bridge.peng_channel_all_positions(),
            "/api/peng/direction": lambda: self.ml_bridge.peng_direction_all_positions(),
            "/api/peng/extreme": lambda: self.ml_bridge.peng_extreme_rules(),
            "/api/peng/tickets": lambda: self.ml_bridge.peng_generate_tickets(
                n=qint(q, "n", 3),
                use_channel=qbool(q, "channel", True),
                use_direction=qbool(q, "direction", True),
                use_extreme=qbool(q, "extreme", True)),
            "/api/peng/blue": lambda: self.ml_bridge.peng_blue_prediction(),
        }
        fn = dispatch.get(clean)
        return self._json(fn() if fn else {"ok": False, "msg": "未知端点"})

    # ── 子路由: 蓝球独立出号 ──

    def _handle_blue_get(self, path):
        q = _parse_query(path)
        return self._json(self.ml_bridge.blue_pick(
            use_freq_blue=qbool(q, "freq_blue", True),
            five_period=qbool(q, "five_period"),
            pattern_rules=qbool(q, "pattern_rules")))

    # ── 子路由: 红球独立出号 ──

    def _handle_red_get(self, path):
        q = _parse_query(path)
        soft = qbool(q, "soft") or qbool(q, "adv_filter")
        div_raw = qint(q, "div")
        diversity_mode = {0: None, 1: "greedy"}.get(div_raw, None)
        mo = qint(q, "max_overlap", -1)
        max_overlap = None if mo < 0 else mo
        return self._json(self.ml_bridge.red_pick(
            n=qint(q, "n", 3), soft=soft,
            diversity_mode=diversity_mode, max_overlap=max_overlap))
    def _handle_covering_get(self, path):
        q = _parse_query(path)
        return self._json(self.ml_bridge.generate_covering(v=qint(q, "v", 15), t=qint(q, "t", 4)))

    def _handle_covering_diverse(self, path):
        q = _parse_query(path)
        mo = qint(q, "max_overlap", -1)
        return self._json(self.ml_bridge.generate_covering_diverse(
            v=qint(q, "v", 15), t=qint(q, "t", 4), n=qint(q, "n", 6),
            max_overlap=None if mo < 0 else mo))

    # ── 子路由: 奖项评估 ──

    def _handle_evaluate_get(self, path):
        n = qint(_parse_query(path), "n", 3)
        tickets = self.ml_bridge.micro_3_tickets(n=n)
        if not tickets.get("tickets"):
            return self._json({"ok": False, "msg": "无法生成票集"})
        result = self.ml_bridge.evaluate_prizes(tickets["tickets"])
        result["tickets"] = tickets["tickets"]
        result["ok"] = True
        return self._json(result)

    # ── 子路由: 对比 ──

    def _handle_compare_get(self, path):
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
        try:
            q = _parse_query(path)
            if qbool(q, "stats"):
                return self._json({"ok": True, "stats": db.prediction_log_stats()})
            period = qint(q, "period", 0) or None
            return self._json({"ok": True, "entries": db.load_prediction_log(
                limit=qint(q, "limit", 100), period=period)})
        except Exception as e:
            import traceback
            return self._json({"ok": False, "msg": f"prediction_log error: {e}", "trace": traceback.format_exc()})

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

        if p == "/api/zone-break/filter":
            payload = self._parse_body()
            if not payload:
                return
            return self._json(self.ml_bridge.filter_zone_break(
                payload.get("break_rows", "000"),
                payload.get("break_cols", "000")))

        if p == "/api/weier/manual":
            payload = self._parse_body()
            if not payload:
                return
            return self._json(self.ml_bridge.generate_weier_manual(payload))

        if p == "/api/prediction-log":
            return self._handle_prediction_log_post()

        self._json({"ok": False, "msg": "404 Not Found"}, code=404)
        return

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