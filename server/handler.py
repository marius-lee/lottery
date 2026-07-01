"""HTTP请求处理器 — 路由分发"""
import http.server
import json
import urllib.parse
from pathlib import Path

from server.query_parser import qbool, qint
from server import db, fetcher

ROOT = Path(__file__).parent.parent
HTML_PATH = ROOT / "index.html"


def _parse_query(path):
    qs = urllib.parse.urlparse(path).query
    return {k: v[0] if v else '' for k, v in urllib.parse.parse_qs(qs).items()}


def _compute_hits(user_reds_set, user_blue, draw):
    """共享: 计算红球命中数和蓝球命中. draw = (period, r1..r6, blue)."""
    draw_reds = set(draw[1:7])
    return len(user_reds_set & draw_reds), 1 if user_blue == draw[7] else 0


class Handler(http.server.BaseHTTPRequestHandler):

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

    # ═══ GET ═══

    def do_GET(self):
        p = self.path
        if p == "/":
            return self._html()

        clean = p.split("?")[0]
        q = _parse_query(p)

        # ── 精确匹配路由 ──
        exact = {
            "/api/data":         self._api_data,
            "/api/fetch":        lambda: self._api_fetch(p),
            "/api/user-picks":   lambda: self._json({"ok": True, "picks": db.load_user_picks()}),
            "/api/stats":        self._api_stats,
            "/api/rules/status": self._api_rules_status,
            "/api/recent-bias":  lambda: self._api_recent_bias(q),
            "/api/signals":      self._api_signals,
            "/api/backtest":     self._api_backtest,
        }
        if clean in exact:
            return exact[clean]()

        # ── 前缀匹配路由 ──
        if p.startswith("/api/micro/"):
            return self._json(self._api_micro_tickets(p))
        if p.startswith("/api/compare"):
            return self._api_compare_get()
        if p.startswith("/static/"):
            return self._serve_static()

        self._json({"ok": False, "msg": "404 Not Found"}, code=404)

    # ── API: 数据 ──

    def _api_data(self):
        data = db.load_draws()
        return self._json({
            "ok": True, "source": "本地数据库",
            "count": min(len(data), 300), "total": len(data),
            "data": data[-300:],
        })

    # ── API: 拉取 ──

    def _api_fetch(self, path):
        q = _parse_query(path)
        force = qbool(q, "force")
        source_name, short_data, new_count = fetcher.fetch_data(force=force)
        if short_data:
            resp = {"ok": True, "source": source_name,
                    "count": len(short_data), "newCount": new_count, "data": short_data}
            picks = db.load_user_picks()
            if picks:
                resp["userPicks"] = picks
        else:
            resp = {"ok": False, "msg": "所有数据源均失败"}
        return self._json(resp)

    # ── API: 出号 ──

    def _api_micro_tickets(self, path):
        from ml.micro_portfolio import generate_tickets
        if path == "/api/micro/3tickets":
            return generate_tickets(n=3)
        q = _parse_query(path)
        n = qint(q, "n", 3)
        soft = qbool(q, "adv_filter") or qbool(q, "soft")
        mo = qint(q, "max_overlap", -1)
        max_overlap = None if mo < 0 else mo
        return generate_tickets(
            n=n, soft=soft, max_overlap=max_overlap,
            use_freq_blue=qbool(q, 'freq_blue'),
        )

    # ── API: 规则状态 ──

    def _api_rules_status(self):
        from ml.micro_portfolio import rule_status
        return self._json({"ok": True, **rule_status()})

    # ── API: 近期偏差 ──

    def _api_recent_bias(self, q):
        from ml.recent_bias import bias_summary
        return self._json(bias_summary(db.load_draws(), window=qint(q, "window", 100)))

    # ── API: 对比(历史) ──

    def _api_compare_get(self):
        conn = db.get_db()
        ready = conn.execute("""
            SELECT DISTINCT up.period FROM user_picks up
            WHERE EXISTS (SELECT 1 FROM draws d WHERE d.period = up.period)
            ORDER BY up.period DESC LIMIT 20
        """).fetchall()
        conn.close()
        return self._json({"ok": True, "readyPeriods": [r[0] for r in ready]})

    # ── API: 统计 ──

    def _api_stats(self):
        conn = db.get_db()
        draw_count = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        pick_count = conn.execute("SELECT COUNT(*) FROM user_picks").fetchone()[0]

        # 一次 JOIN 替代 N+1
        rows = conn.execute("""
            SELECT up.period, up.r1, up.r2, up.r3, up.r4, up.r5, up.r6, up.blue,
                   up.strategy, up.created_at,
                   d.r1 as dr1, d.r2 as dr2, d.r3 as dr3, d.r4 as dr4, d.r5 as dr5, d.r6 as dr6, d.blue as dblue
            FROM user_picks up
            LEFT JOIN draws d ON d.period = up.period
            ORDER BY up.period
        """).fetchall()
        conn.close()

        hit_stats = []
        for r in rows:
            if r["dr1"] is None:
                continue
            user_set = {r["r1"], r["r2"], r["r3"], r["r4"], r["r5"], r["r6"]}
            draw_set = {r["dr1"], r["dr2"], r["dr3"], r["dr4"], r["dr5"], r["dr6"]}
            rh = len(user_set & draw_set)
            bh = 1 if r["blue"] == r["dblue"] else 0
            hit_stats.append({
                "period": r["period"], "red_hits": rh,
                "blue_hit": bh, "strategy": r["strategy"],
            })

        return self._json({
            "ok": True, "drawCount": draw_count, "pickCount": pick_count,
            "hitStats": hit_stats[-50:],
        })

    # ── API: 多算法信号 ──

    def _api_signals(self):
        """返回四种算法的信号摘要."""
        from ml.signal_aggregator import collect_all_signals
        data = db.load_draws()
        fused_w, diag = collect_all_signals(data)
        # 提取偏热号码 (fused > 1.1)
        hot = [(n, round(fused_w[n], 3)) for n in range(1, 34) if fused_w[n] > 1.1]
        hot.sort(key=lambda x: -x[1])
        return self._json({
            "ok": True,
            "hot_numbers": hot[:12],
            "weights": [round(fused_w[n], 3) for n in range(1, 34)],
            "algorithms": diag,
        })

    # ── API: 回测 ──

    def _api_backtest(self):
        from ml.signal_aggregator import run_all_backtests
        data = db.load_draws()
        if len(data) < 300:
            return self._json({"ok": False, "msg": "至少需要300期数据"})
        results = run_all_backtests(data)
        return self._json({"ok": True, "results": results})

    # ═══ Static ═══

    def _serve_static(self):
        file_path = ROOT / self.path.lstrip("/")
        if not file_path.resolve().is_relative_to(ROOT.resolve()):
            self.send_response(403); self.end_headers(); return
        if not file_path.is_file():
            self.send_response(404); self.end_headers(); return
        ct = "text/css" if file_path.suffix == ".css" else "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    # ═══ POST ═══

    def do_POST(self):
        if self.path == "/api/save":
            return self._api_save_post()
        if self.path == "/api/compare":
            return self._api_compare_post()
        self._json({"ok": False, "msg": "404 Not Found"}, code=404)

    def _parse_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self.send_response(400); self.end_headers()

    # ── POST: 保存 ──

    def _api_save_post(self):
        payload = self._parse_body()
        if not payload:
            return
        for p in payload.get("picks", []):
            db.insert_user_pick(
                period=p["period"], reds=p["reds"], blue=p["blue"],
                strategy=p.get("strategy", ""),
            )
        return self._json({"ok": True, "saved": len(payload.get("picks", []))})

    # ── POST: 对比 ──

    def _api_compare_post(self):
        payload = self._parse_body()
        if not payload:
            return
        period = int(payload["period"])
        actual_reds = set(int(x) for x in payload["reds"])
        actual_blue = int(payload["blue"])

        conn = db.get_db()

        # 确保开奖数据存在
        existing = conn.execute("SELECT 1 FROM draws WHERE period=?", (period,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO draws (period, r1, r2, r3, r4, r5, r6, blue, source) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [period] + sorted(actual_reds) + [actual_blue, "用户录入"],
            )
            conn.commit()

        # 兑奖: user_picks
        rows = conn.execute(
            "SELECT id, r1, r2, r3, r4, r5, r6, blue, strategy FROM user_picks WHERE period=?",
            (period,),
        ).fetchall()

        picks = []
        strat_hits = {}
        for p in rows:
            user_set = {p[1], p[2], p[3], p[4], p[5], p[6]}
            rh, bh = _compute_hits(user_set, p[7], [period] + [p[1],p[2],p[3],p[4],p[5],p[6],p[7]])
            # 实际计算
            rh = len(user_set & actual_reds)
            bh = 1 if p[7] == actual_blue else 0
            strat = p[8] or "unknown"
            picks.append({"reds": sorted(user_set), "blue": p[7], "strategy": strat,
                          "red_hits": rh, "blue_hit": bh})
            if strat not in strat_hits:
                strat_hits[strat] = {"hits": 0, "tries": 0, "red_hits_sum": 0, "blue_hits": 0}
            s = strat_hits[strat]
            s["tries"] += 1; s["red_hits_sum"] += rh; s["blue_hits"] += bh
            if rh >= 3 or bh == 1:
                s["hits"] += 1

        conn.commit()
        conn.close()

        return self._json({
            "ok": True, "period": period, "pickCount": len(picks),
            "picks": picks, "strategyPerformance": strat_hits,
        })
