"""定时调度器 — 双色球每周二/四/日 22:00 自动拉取开奖数据并兑奖.

双色球开奖时间: 每周二、四、日 21:15 开奖, 22:00 各平台公布号码.
调度器在 22:05 触发, 给数据源留 5 分钟缓冲.

用法:
  from server.scheduler import start_scheduler, schedule_status
  start_scheduler()  # daemon线程, 不阻塞
  status = schedule_status()
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


# 全局状态 (线程安全用锁保护)
_lock = threading.Lock()
_state: Dict[str, Any] = {
    "running": False,
    "next_fetch_at": None,
    "last_fetch_at": None,
    "last_fetch_result": None,
    "fetch_count": 0,
    "error": None,
}

# 双色球开奖日: 周二=1, 周四=3, 周日=6 (Python weekday: Mon=0)
_DRAW_WEEKDAYS = {1, 3, 6}  # Tuesday, Thursday, Sunday
_FETCH_HOUR = 22
_FETCH_MINUTE = 5
_POLL_INTERVAL = 60  # 睡眠期间每60秒检查一次


def _next_draw_time(now: Optional[datetime] = None) -> datetime:
    """计算下一个二/四/日 22:05 的时间.

    Args:
        now: 当前时间, None 则用系统时间

    Returns:
        下次触发的 datetime 对象
    """
    if now is None:
        now = datetime.now()

    # 从今天开始往后找下一个开奖日
    for offset in range(8):  # 最多找8天, 确保找到
        candidate = now + timedelta(days=offset)
        target = candidate.replace(hour=_FETCH_HOUR, minute=_FETCH_MINUTE, second=0, microsecond=0)

        if candidate.weekday() in _DRAW_WEEKDAYS and target > now:
            return target

    # 理论上不会到这
    return now + timedelta(days=1)


def _fetch_and_claim():
    """执行数据拉取 + 自动兑奖."""
    global _state
    print(f"\n[Scheduler] {datetime.now().strftime('%H:%M:%S')} — 定时拉取触发")

    try:
        from server import fetcher, db
        from server.auto_claim import auto_claim_all

        source, _, count = fetcher.fetch_data(force=True)
        result = {
            "source": source,
            "new_count": count,
            "total_draws": db.count_draws(),
        }

        print(f"[Scheduler] 拉取: {source}, 新增 {count} 期")

        # 自动兑奖
        if count > 0:
            claim = auto_claim_all()
            result["claimed"] = claim["claimed"]
            result["new_periods"] = claim["total_new_periods"]
            if claim.get("recalculated"):
                result["weights_updated"] = True
                print(f"[Scheduler] 兑奖 {claim['claimed']} 注, 权重已更新")
            else:
                print(f"[Scheduler] 兑奖 {claim['claimed']} 注")
        else:
            # 即使无新增, 也跑一次兑奖 (可能有手动录入的数据未兑)
            claim = auto_claim_all()
            if claim["claimed"] > 0:
                result["claimed_retro"] = claim["claimed"]

        with _lock:
            _state["last_fetch_at"] = datetime.now().isoformat()
            _state["last_fetch_result"] = result
            _state["fetch_count"] += 1
            _state["error"] = None

    except Exception as e:
        with _lock:
            _state["last_fetch_at"] = datetime.now().isoformat()
            _state["last_fetch_result"] = None
            _state["error"] = str(e)
        print(f"[Scheduler] 错误: {e}")


def _scheduler_loop():
    """后台调度线程 — 循环计算下次时间并等待."""
    global _state

    with _lock:
        _state["running"] = True

    print(f"[Scheduler] 启动 — 双色球每周二/四/日 {_FETCH_HOUR}:{_FETCH_MINUTE:02d} 自动拉取")

    while True:
        next_time = _next_draw_time()
        with _lock:
            _state["next_fetch_at"] = next_time.isoformat()

        wait_seconds = max(1, (next_time - datetime.now()).total_seconds())
        hours = wait_seconds / 3600
        print(f"[Scheduler] 下次拉取: {next_time.strftime('%m-%d %a %H:%M')} (还有 {hours:.1f}h)")

        # 分段睡眠, 允许优雅退出
        while wait_seconds > 0:
            sleep_for = min(_POLL_INTERVAL, wait_seconds)
            time.sleep(sleep_for)
            wait_seconds -= sleep_for

        # 执行拉取 + 兑奖
        _fetch_and_claim()


def start_scheduler():
    """启动后台调度线程 (daemon)."""
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="ssq-scheduler")
    t.start()
    return t


def schedule_status() -> Dict[str, Any]:
    """返回调度器当前状态 — 供 API 使用."""
    with _lock:
        status = dict(_state)
    status["next_fetch_at_readable"] = (
        _next_draw_time().strftime("%Y-%m-%d %a %H:%M")
    )
    return status
