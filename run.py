#!/usr/bin/env python3
"""开发服务器 — 自动重启模式

用法:
  python3 run.py          # 启动 + 自动重启
  python3 app.py          # 直接启动 (不重启)

监控 ml/ server/ static/ 下的 .py/.js/.css/.html 文件,
任何变更 → 杀掉旧进程 → 马上重启。
"""
import os
import subprocess
import sys
import time

WATCH_DIRS = ["ml", "server", "static"]
WATCH_EXTS = {".py", ".js", ".css", ".html"}


def collect_mtimes():
    mtimes = {}
    for d in WATCH_DIRS:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if os.path.splitext(f)[1] in WATCH_EXTS:
                    path = os.path.join(root, f)
                    try:
                        mtimes[path] = os.path.getmtime(path)
                    except OSError:
                        pass
    try:
        mtimes["app.py"] = os.path.getmtime("app.py")
    except OSError:
        pass
    return mtimes


def main():
    python = sys.executable
    proc = None
    baseline = None
    restart_count = 0
    max_restarts = 20  # 防止无限重启
    backoff_base = 0.5  # 首次退避 0.5s

    while restart_count < max_restarts:
        # 启动
        print(f"\n▶ 启动服务器...", flush=True)
        proc = subprocess.Popen([python, "app.py"],
                                stdout=sys.stdout, stderr=sys.stderr)
        restart_count += 1
        baseline = collect_mtimes()

        # 检查是否立刻崩溃
        time.sleep(0.5)
        if proc.poll() is not None and proc.returncode != 3:
            # 非 reload 退出 — 真正的错误 (如端口占用)
            print(f"  ❌ 服务器异常退出 (code={proc.returncode})，{3-restart_count}次重试后停止",
                  flush=True)
            time.sleep(backoff_base * restart_count)
            continue

        # 监控循环
        try:
            while proc.poll() is None:
                time.sleep(1)
                current = collect_mtimes()
                changed = [p for p, mt in current.items()
                           if p not in baseline or mt > baseline.get(p, 0) + 0.1]
                # 新增文件
                changed += [p for p in current if p not in baseline]
                if changed:
                    names = sorted(set(os.path.relpath(p) for p in changed))
                    preview = names[:3]
                    more = f" (+{len(names)-3})" if len(names) > 3 else ""
                    print(f"\n🔁 检测到变更: {', '.join(preview)}{more}",
                          flush=True)
                    print("   重启中...\n", flush=True)
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    time.sleep(0.3)
                    break  # 跳出监控循环, 回到外层重启
                baseline = current
        except KeyboardInterrupt:
            print("\n🛑 停止中...", flush=True)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            break


if __name__ == "__main__":
    main()
