"""中彩网数据抓取 (Facade Pattern) — Cookie会话 + 自动重试 + 增量更新"""
import http.cookiejar
import json
import re
import ssl
import sys
import urllib.request

from server import db

CACHE_MAX_AGE = 6 * 3600       # 6小时缓存
FETCH_COUNT = 20               # 增量拉取期数（覆盖约4周缺口）

_cwl_opener = None


def _get_cwl_opener():
    global _cwl_opener
    if _cwl_opener is not None:
        return _cwl_opener
    ctx = ssl.create_default_context()
    # SSL 验证启用: 中彩网使用正规 CA 证书, 无需关闭验证
    https_handler = urllib.request.HTTPSHandler(context=ctx)
    cj = http.cookiejar.CookieJar()
    cookie_handler = urllib.request.HTTPCookieProcessor(cj)
    _cwl_opener = urllib.request.build_opener(https_handler, cookie_handler)
    return _cwl_opener


def _parse_ssq_items(data):
    items = data.get("result", data.get("data", []))
    if isinstance(items, dict):
        items = items.get("list", items.get("records", []))
    if not isinstance(items, list):
        return []
    results = []
    for item in items:
        code = item.get("code", item.get("drawNum", ""))
        red = item.get("red", "")
        blue = item.get("blue", "")
        if not code or not red:
            continue
        reds = [int(x) for x in re.split(r'[|, ]+', red) if x.strip().isdigit()]
        blues = [int(x) for x in re.split(r'[|, ]+', blue) if x.strip().isdigit()]
        if len(reds) == 6 and len(blues) >= 1:
            try:
                results.append([int(code)] + reds + [blues[0]])
            except ValueError:
                continue
    results.sort(key=lambda r: r[0])
    return results


def fetch_from_cwl(count=FETCH_COUNT, retry=True):
    url = (
        "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/"
        f"findDrawNotice?name=ssq&issueCount={count}"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.cwl.gov.cn/ygkj/ssq/kjgg/",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        opener = _get_cwl_opener()
        resp = opener.open(req, timeout=20)
        body = json.loads(resp.read().decode("utf-8"))
        return _parse_ssq_items(body)
    except Exception:
        if retry:
            global _cwl_opener
            _cwl_opener = None
            return fetch_from_cwl(count, retry=False)
        raise


def _latest_db_period():
    all_data = db.load_draws()
    if not all_data:
        return 0
    return all_data[-1][0]


def fetch_data(force=False):
    """获取开奖数据。

    force=False: 缓存未过期 → 直接读 SQLite
    force=True:  拉取 FETCH_COUNT 期 → 过滤 >DB最新期号 → INSERT 新的

    返回 (source_name, short_data, new_count)
    """
    # 非强制 → 读本地
    if not force and db.count_draws() > 0 and db.last_fetch_age() < CACHE_MAX_AGE:
        all_data = db.load_draws()
        short = all_data[-300:] if len(all_data) > 300 else all_data
        return "本地数据库", short, 0

    # 强制刷新 → 增量拉取
    try:
        latest = _latest_db_period()
        results = fetch_from_cwl(FETCH_COUNT)
        if not results:
            raise Exception("空结果")

        # 只保留比数据库新的
        new = [r for r in results if r[0] > latest]

        if new:
            db.upsert_draws(new, "中彩网")
            db.set_fetch_time()

            # 使分析管道失效, 下次请求自动重建
            try:
                pass  # pipeline 已删除
            except Exception:
                pass

        all_data = db.load_draws()
        short = all_data[-300:] if len(all_data) > 300 else all_data
        return f"中彩网(新增{len(new)}期)", short, len(new)

    except Exception as e:
        print(f"  [中彩网] 失败: {e}", file=sys.stderr)

    # API 失败 → 降级读本地
    fallback = db.load_draws()
    if fallback:
        short = fallback[-300:] if len(fallback) > 300 else fallback
        return "数据库(离线)", short, 0

    return None, None, 0
