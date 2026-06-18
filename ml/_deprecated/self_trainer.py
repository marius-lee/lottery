"""自训练引擎 v5 — 全局变量 + 原子更新

架构:
  CURRENT_TARGET  最新期号 (cron写, 训练读)
  TRAIN_DATA      最新期之前的全部数据 (cron写, 训练读)
  ACTUAL_RESULT   最新期真实开奖 (set(红球), 蓝球)

  cron: 周二/四/日 21:30 拉取中彩网 → 原子更新三个全局变量
  训练: 循环直接读全局变量, 不查数据库
  启动: 从 SQLite 初始化全局变量
"""

import json
import time
import random
import threading
from pathlib import Path
from server import db

ROOT = Path(__file__).parent.parent
PRED_DIR = ROOT / ".cache" / "predictions"
CKPT_DIR = ROOT / ".cache" / "checkpoints"
PRED_DIR.mkdir(parents=True, exist_ok=True)
CKPT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# 全局变量 (cron线程写入, 训练线程只读)
# ═══════════════════════════════════════════════════════════════════

CURRENT_TARGET = None        # int: 最新期号
TRAIN_DATA = []              # list: 最新期之前的全部[[period, r1..r6, blue], ...]
ACTUAL_RESULT = None         # (set(reds), blue): 最新期真实开奖

WINDOW_POOL = [8, 10, 12, 15]
# Dropout 0.1-0.2: Srivastava et al. (2014) JMLR https://dl.acm.org/doi/10.5555/2627435.2670313
DROPOUT_POOL = [0.1, 0.15, 0.2]

# ═══════════════════════════════════════════════════════════════════
# 初始化 / 更新
# ═══════════════════════════════════════════════════════════════════

def init_from_db():
    """启动时从 SQLite 初始化全局变量"""
    global CURRENT_TARGET, TRAIN_DATA, ACTUAL_RESULT
    data = db.load_draws()
    if not data:
        return False
    latest = data[-1]
    CURRENT_TARGET, TRAIN_DATA = latest[0], data[:-1]
    ACTUAL_RESULT = (set(latest[1:7]), latest[7])
    return True

def fetch_and_update():
    """cron: 拉取中彩网最新数据, 原子更新全局变量"""
    global CURRENT_TARGET, TRAIN_DATA, ACTUAL_RESULT
    from server import fetcher
    fetcher.fetch_data(force=True)
    data = db.load_draws()
    if not data:
        return
    latest = data[-1]
    CURRENT_TARGET, TRAIN_DATA = latest[0], data[:-1]
    ACTUAL_RESULT = (set(latest[1:7]), latest[7])
    print(f"[Cron] updated: target={CURRENT_TARGET}, train_size={len(TRAIN_DATA)}")

# ═══════════════════════════════════════════════════════════════════
# 预测快照 / 3注缓存
# ═══════════════════════════════════════════════════════════════════

def _save_pred(model, reds, blue, red_hits, best_so_far, round_num=None):
    with open(PRED_DIR / f"{model}_prediction.json", "w") as f:
        json.dump({"model": model, "reds": reds, "blue": blue,
                   "target_period": CURRENT_TARGET, "red_hits": red_hits,
                   "best_so_far": best_so_far, "round_number": round_num,
                   "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f)

# ═══════════════════════════════════════════════════════════════════
# 调度
# ═══════════════════════════════════════════════════════════════════

def start_training_thread(gpt):
    """app.py 调用: 初始化+启动后台线程. gpt 是共享模型实例."""
    if not init_from_db():
        print("[Trainer] No data"); return
    print(f"[Trainer] target={CURRENT_TARGET}, train={len(TRAIN_DATA)} draws")

    def cron_loop():
        while True:
            now = time.localtime()
            if now.tm_wday in (1,3,6) and now.tm_hour==21 and now.tm_min==30:
                fetch_and_update()
            time.sleep(60)

    threading.Thread(target=cron_loop, daemon=True).start()

    from ml.training_optimizers import compute_autocorr_lr_bounds, cyclic_lr
    from ml.ewc_soup import EWCRegularizer, ModelSoup

    best_red = [-1]
    lr_lo, lr_hi = compute_autocorr_lr_bounds(TRAIN_DATA)
    ewc = EWCRegularizer(gpt.model, lambda_ewc=100.0)
    if not ewc.load(): ewc.update_and_save(gpt.model)
    soup = ModelSoup(max_checkpoints=5)
    rsb = [0]

    def train_loop():
        nonlocal lr_lo, lr_hi
        round_num = 0
        while True:
            round_num += 1
            t0 = time.time()
            ws = random.choice(WINDOW_POOL)
            do = random.choice(DROPOUT_POOL)
            lr = cyclic_lr(round_num, 50, lr_lo, lr_hi)
            try:
                gpt.continue_train(TRAIN_DATA, epochs=2, block_size=256, ewc_reg=ewc)
                ewc_loss_val = ewc.ewc_loss(gpt.model)
                pred = gpt.predict(TRAIN_DATA, temperature=0.8)
                red_hits = len(set(pred["reds"]) & ACTUAL_RESULT[0])
                blue_hit = 1 if pred["blue"] == ACTUAL_RESULT[1] else 0
            except Exception as e:
                db.insert_training_log("gpt", round_num, "validate", CURRENT_TARGET,
                                       loss=-1, notes=f"error: {e}", duration_sec=time.time()-t0)
                continue
            dur = time.time() - t0
            if red_hits > best_red[0]:
                best_red[0] = red_hits; rsb[0] = 0
                gpt.model.save(str(CKPT_DIR / "gpt_best.keras"))
                gpt.save_swa()
                ewc.update_and_save(gpt.model)
                soup.add(red_hits * 10 + blue_hit, str(CKPT_DIR / "gpt_best.keras"))
                _save_pred("gpt", pred["reds"], pred["blue"], red_hits, True, round_num)
                lr_lo, lr_hi = compute_autocorr_lr_bounds(TRAIN_DATA)
            else:
                rsb[0] += 1
            if rsb[0] >= 100 and soup.checkpoints:
                try: soup.greedy_soup(gpt.model); rsb[0] = 0
                except: pass
            db.insert_training_log("gpt", round_num, "validate", CURRENT_TARGET,
                                   red_hits=red_hits, blue_hit=blue_hit, loss=ewc_loss_val,
                                   window_size=ws, learning_rate=lr, dropout=do,
                                   duration_sec=round(dur,1), best_so_far=1 if red_hits > best_red[0] else 0)
            if round_num % 10 == 0:
                print(f"[GPT] r{round_num}: {red_hits}R+{blue_hit}B best={best_red[0]} "
                      f"swa={gpt._swa_count} ewc={ewc_loss_val:.1f} {dur:.1f}s")

    threading.Thread(target=train_loop, daemon=True).start()

    def reporter():
        while True:
            time.sleep(600)
            logs = db.get_best_hits(CURRENT_TARGET) if CURRENT_TARGET else []
            b = f"{logs[0]['best_red']}R+{logs[0]['best_blue']}B" if logs else "N/A"
            print(f"\n=== {time.strftime('%H:%M:%S')}  best={b} ===")
    threading.Thread(target=reporter, daemon=True).start()
    print("[Trainer] Threads started")


def status():
    logs = db.get_best_hits(CURRENT_TARGET) if CURRENT_TARGET else []
    return {"target_period": CURRENT_TARGET, "models": logs}
