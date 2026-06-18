"""
XGBoost 一号码一模型预测器 — v2 精简增强版

特征设计原则:
  只保留时序动态特征(有预测力)。删除静态标记(质数/分区/尾号)。
  新增数据挖掘验证的结构化特征(球位黏性/共现上下文/位置历史)。

来源:
  特征重要性分析 2026-06-08: 质数/分区/尾号贡献=0.0%
  数据结构化扫描 2026-06-08: 球位黏性lift 3-6x, 共现lift 1.1-1.2x
"""

import os
import pickle
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
MODEL_DIR = ROOT / ".cache" / "xgb_models"


def _get_position(draw_reds_sorted, target_num):
    """目标号码在本期红球中的排序位置(1-6)。未出现返回0。"""
    for pos, r in enumerate(draw_reds_sorted, 1):
        if r == target_num:
            return pos
    return 0


def build_features(draws, target_num, is_red=True):
    """为单个号码构建训练特征 (14维)。

    F1-F2:  短期出现标记
    F3-F7:  多窗口频率计数
    F8:     当前遗漏
    F9:     趋势(近15期 vs 远15期)
    F10:    平均出球间隔
    F11:    相对遗漏(遗漏/均隔, >1=逾期)
    ——— 删除 F12质数 F13一区 F14二区 F15尾号 (贡献=0.0%) ———
    F12:    最近出现位置(1-6, 0=上期未出现)
    F13:    球位黏性得分(lift, >1=同位置易重复)
    F14:    共现上下文(与上期号码的平均共现lift)

    Args:
        draws: [[period, r1..r6, blue], ...] sorted by period ascending
        target_num: 1-33 (red) or 1-16 (blue)
        is_red: True for red ball, False for blue

    Returns:
        X: (N, 14) feature matrix
        y: (N,) binary labels (1 = appeared)
    """
    N = len(draws)
    if N < 5:
        return np.array([]).reshape(0, 14), np.array([])

    X_list, y_list = [], []

    for i in range(5, N):
        feats = []

        # ── 窗口数据 ──
        curr_reds = sorted(draws[i][1:7]) if is_red else None
        prev_reds = sorted(draws[i - 1][1:7]) if is_red else None
        prev_set = set(prev_reds) if is_red else {draws[i - 1][7]}

        # F1-F2: 近1/2期出现
        feats.append(1 if target_num in prev_set else 0)
        prev2_set = set(draws[i - 2][1:7]) if is_red else {draws[i - 2][7]}
        feats.append(1 if target_num in prev2_set else 0)

        # F3-F7: 多窗口频率计数
        for window in [3, 5, 10, 20, 30]:
            start = max(0, i - window)
            cnt = 0
            for j in range(start, i):
                if is_red:
                    if target_num in draws[j][1:7]:
                        cnt += 1
                elif draws[j][7] == target_num:
                    cnt += 1
            feats.append(cnt)

        # F8: 当前遗漏
        omission = 0
        for j in range(i - 1, -1, -1):
            if is_red:
                if target_num in draws[j][1:7]:
                    break
            elif draws[j][7] == target_num:
                break
            omission += 1
        feats.append(omission)

        # F9: 趋势 (近15 vs 远15)
        recent_15 = max(0, i - 15)
        older_15 = max(0, i - 30)
        rc, oc = 0, 0
        for j in range(recent_15, i):
            if is_red:
                if target_num in draws[j][1:7]: rc += 1
            elif draws[j][7] == target_num: rc += 1
        for j in range(older_15, recent_15):
            if is_red:
                if target_num in draws[j][1:7]: oc += 1
            elif draws[j][7] == target_num: oc += 1
        feats.append(rc - oc)

        # F10: 平均间隔
        appearances = []
        for j in range(i):
            if is_red:
                if target_num in draws[j][1:7]:
                    appearances.append(j)
            elif draws[j][7] == target_num:
                appearances.append(j)
        if len(appearances) >= 2:
            gaps = [appearances[k + 1] - appearances[k] for k in range(len(appearances) - 1)]
            avg_interval = sum(gaps) / len(gaps)
        else:
            avg_interval = float(i)
        feats.append(avg_interval)

        # F11: 相对遗漏
        feats.append(omission / max(1, avg_interval))

        # ── 新增结构化特征 (红球专用) ──
        if is_red:
            # F12: 最近出现位置 (1-6, 0=上期未出现)
            last_pos = _get_position(prev_reds, target_num)
            feats.append(float(last_pos))

            # F13: 球位黏性得分
            # 计算: 历史中该号码在同位置重复出现的频率 / 理论随机频率
            if last_pos > 0:
                # 统计历史中该号码出现在last_pos后下一期又出现在last_pos的次数
                stick_count = 0
                total_at_pos = 0
                for j in range(1, i):
                    prev_draw_reds = sorted(draws[j - 1][1:7])
                    pos_j = _get_position(prev_draw_reds, target_num)
                    if pos_j == last_pos:
                        total_at_pos += 1
                        curr_draw_reds = sorted(draws[j][1:7])
                        if _get_position(curr_draw_reds, target_num) == last_pos:
                            stick_count += 1
                if total_at_pos >= 3:
                    stick_rate = stick_count / total_at_pos
                    feats.append(stick_rate * 33)  # 标准化: ×33使期望≈1
                else:
                    feats.append(1.0)
            else:
                feats.append(1.0)

            # F14: 共现上下文 — 与上期号码的平均共现lift
            cooc_sum = 0.0
            prev_balls = list(prev_set)
            if prev_balls:
                for pb in prev_balls:
                    if pb == target_num:
                        continue
                    # 统计历史中共现频率
                    ab = 0  # A和B同时出现的期数
                    a_count = 0  # A出现的期数
                    for j in range(i):
                        draw_reds = draws[j][1:7]
                        has_target = target_num in draw_reds
                        has_pb = pb in draw_reds
                        if has_pb:
                            a_count += 1
                        if has_target and has_pb:
                            ab += 1
                    if a_count >= 5:
                        p_ba = ab / a_count
                        # 边际概率 P(target)
                        p_target = sum(1 for j in range(i) if target_num in draws[j][1:7]) / i
                        if p_target > 0:
                            lift = p_ba / p_target
                            cooc_sum += lift
                cooc_avg = cooc_sum / len(prev_balls)
            else:
                cooc_avg = 1.0
            feats.append(float(np.clip(cooc_avg, 0.3, 3.0)))
        else:
            # Blue ball: 填充中性值
            feats.append(0.0)  # F12 placeholder
            feats.append(1.0)  # F13 placeholder
            feats.append(1.0)  # F14 placeholder

        X_list.append(feats)

        # Label
        if is_red:
            y_list.append(1 if target_num in curr_reds else 0)
        else:
            y_list.append(1 if draws[i][7] == target_num else 0)

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


def build_next_features(draws, target_num, is_red=True):
    """为下一期预测构建特征 (14维, 与 build_features v2 严格对齐)。

    F1-11: 时序动态特征 (同前)
    F12: 最近出现位置 (1-6, 0=上期未出现)
    F13: 球位黏性得分
    F14: 共现上下文
    """
    if len(draws) < 5:
        return None
    N = len(draws)
    feats = []

    prev_reds = sorted(draws[N - 1][1:7]) if is_red else None
    prev_set = set(prev_reds) if is_red else {draws[N - 1][7]}

    # F1-F2: 近1/2期出现
    feats.append(1 if target_num in prev_set else 0)
    prev2_set = set(draws[N - 2][1:7]) if is_red else {draws[N - 2][7]}
    feats.append(1 if target_num in prev2_set else 0)

    # F3-F7: 多窗口计数
    for window in [3, 5, 10, 20, 30]:
        start = max(0, N - window)
        cnt = 0
        for j in range(start, N):
            if is_red:
                if target_num in draws[j][1:7]: cnt += 1
            elif draws[j][7] == target_num: cnt += 1
        feats.append(cnt)

    # F8: 当前遗漏
    omission = 0
    for j in range(N - 1, -1, -1):
        if is_red:
            if target_num in draws[j][1:7]: break
        elif draws[j][7] == target_num: break
        omission += 1
    feats.append(omission)

    # F9: 趋势
    recent_15 = max(0, N - 15)
    older_15 = max(0, N - 30)
    rc, oc = 0, 0
    for j in range(recent_15, N):
        if is_red:
            if target_num in draws[j][1:7]: rc += 1
        elif draws[j][7] == target_num: rc += 1
    for j in range(older_15, recent_15):
        if is_red:
            if target_num in draws[j][1:7]: oc += 1
        elif draws[j][7] == target_num: oc += 1
    feats.append(rc - oc)

    # F10: 平均间隔
    appearances = []
    for j in range(N):
        if is_red:
            if target_num in draws[j][1:7]: appearances.append(j)
        elif draws[j][7] == target_num: appearances.append(j)
    if len(appearances) >= 2:
        gaps = [appearances[k + 1] - appearances[k] for k in range(len(appearances) - 1)]
        avg_interval = sum(gaps) / len(gaps)
    else:
        avg_interval = float(N)
    feats.append(avg_interval)

    # F11: 相对遗漏
    feats.append(omission / max(1, avg_interval))

    # ── 新增结构化特征 ──
    if is_red:
        # F12: 最近出现位置
        last_pos = _get_position(prev_reds, target_num)
        feats.append(float(last_pos))

        # F13: 球位黏性得分
        if last_pos > 0:
            stick_count = 0
            total_at_pos = 0
            for j in range(1, N):
                prev_d = sorted(draws[j - 1][1:7])
                if _get_position(prev_d, target_num) == last_pos:
                    total_at_pos += 1
                    curr_d = sorted(draws[j][1:7])
                    if _get_position(curr_d, target_num) == last_pos:
                        stick_count += 1
            if total_at_pos >= 3:
                feats.append(stick_count / total_at_pos * 33)
            else:
                feats.append(1.0)
        else:
            feats.append(1.0)

        # F14: 共现上下文
        cooc_sum = 0.0
        prev_balls = list(prev_set)
        if prev_balls:
            for pb in prev_balls:
                if pb == target_num:
                    continue
                ab = 0; a_count = 0
                for j in range(N):
                    draw_reds = draws[j][1:7]
                    if pb in draw_reds:
                        a_count += 1
                        if target_num in draw_reds:
                            ab += 1
                if a_count >= 5:
                    p_target = sum(1 for j in range(N) if target_num in draws[j][1:7]) / N
                    if p_target > 0:
                        cooc_sum += (ab / a_count) / p_target
            cooc_avg = cooc_sum / len(prev_balls) if len(prev_balls) > 0 else 1.0
        else:
            cooc_avg = 1.0
        feats.append(float(np.clip(cooc_avg, 0.3, 3.0)))
    else:
        feats.append(0.0)
        feats.append(1.0)
        feats.append(1.0)

    return np.array([feats], dtype=np.float32)


class XGBPredictor:
    """XGBoost 一号码一模型预测器 — 超参数来源: ml.ssq_constants"""

    def __init__(self, model_dir=None):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.models = {}

    def train(self, draws, verbose=False):
        import xgboost as xgb
        from ml.ssq_constants import (
            XGB_N_ESTIMATORS, XGB_MAX_DEPTH, XGB_LEARNING_RATE,
            TOTAL_RED, TOTAL_BLUE,
        )

        self.model_dir.mkdir(parents=True, exist_ok=True)
        trained = 0

        for num in range(1, TOTAL_RED + 1):
            X, y = build_features(draws, num, is_red=True)
            if len(X) < 10:
                continue
            split = int(len(X) * 0.8)
            X_train, y_train = X[:split], y[:split]

            pos_weight = max(1, (len(y_train) - sum(y_train)) / max(1, sum(y_train)))
            model = xgb.XGBClassifier(
                n_estimators=XGB_N_ESTIMATORS, max_depth=XGB_MAX_DEPTH,
                learning_rate=XGB_LEARNING_RATE,
                scale_pos_weight=pos_weight,
                random_state=42, verbosity=0
            )
            model.fit(X_train, y_train)
            key = f"red_{num}"
            self.models[key] = model
            # Save to disk
            with open(self.model_dir / f"{key}.pkl", "wb") as f:
                pickle.dump(model, f)
            trained += 1
            if verbose and num % 10 == 0:
                print(f"  [XGB] red {num}/33 trained")

        # Train blue ball models (1-16)
        for num in range(1, 17):
            X, y = build_features(draws, num, is_red=False)
            if len(X) < 10:
                continue
            split = int(len(X) * 0.8)
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]

            pos_weight = max(1, (len(y_train) - sum(y_train)) / max(1, sum(y_train)))
            model = xgb.XGBClassifier(
                n_estimators=XGB_N_ESTIMATORS, max_depth=XGB_MAX_DEPTH, learning_rate=XGB_LEARNING_RATE,
                scale_pos_weight=pos_weight,
                random_state=42, verbosity=0
            )
            model.fit(X_train, y_train)
            key = f"blue_{num}"
            self.models[key] = model
            with open(self.model_dir / f"{key}.pkl", "wb") as f:
                pickle.dump(model, f)
            trained += 1

        return trained

    def load(self):
        """从磁盘加载已训练的模型。"""
        for num in range(1, 34):
            path = self.model_dir / f"red_{num}.pkl"
            if path.exists():
                with open(path, "rb") as f:
                    self.models[f"red_{num}"] = pickle.load(f)
        for num in range(1, 17):
            path = self.model_dir / f"blue_{num}.pkl"
            if path.exists():
                with open(path, "rb") as f:
                    self.models[f"blue_{num}"] = pickle.load(f)
        return len(self.models)

    def is_trained(self):
        return len(self.models) >= 40  # at least most models loaded

    def predict(self, draws):
        """预测下一期号码。

        Args:
            draws: [[period, r1..r6, blue], ...] sorted ascending

        Returns:
            dict with 'reds' (top 6), 'blue' (top 1), 'red_probs', 'blue_probs'
        """
        red_probs = {}
        for num in range(1, 34):
            key = f"red_{num}"
            if key not in self.models:
                red_probs[num] = 0.0
                continue
            X_next = build_next_features(draws, num, is_red=True)
            if X_next is None:
                red_probs[num] = 0.0
                continue
            prob = float(self.models[key].predict_proba(X_next)[0][1])
            red_probs[num] = prob

        blue_probs = {}
        for num in range(1, 17):
            key = f"blue_{num}"
            if key not in self.models:
                blue_probs[num] = 0.0
                continue
            X_next = build_next_features(draws, num, is_red=False)
            if X_next is None:
                blue_probs[num] = 0.0
                continue
            prob = float(self.models[key].predict_proba(X_next)[0][1])
            blue_probs[num] = prob

        top6_reds = sorted(red_probs, key=lambda x: red_probs[x], reverse=True)[:6]
        top1_blue = max(blue_probs, key=lambda x: blue_probs[x])

        return {
            "reds": sorted(top6_reds),
            "blue": top1_blue,
            "red_probs": {str(k): round(v, 4) for k, v in red_probs.items()},
            "blue_probs": {str(k): round(v, 4) for k, v in blue_probs.items()},
        }

    def validate_oot(self, draws, holdout=50):
        import xgboost as xgb
        from ml.ssq_constants import (
            XGB_N_ESTIMATORS, XGB_MAX_DEPTH, XGB_LEARNING_RATE,
            TOTAL_RED, TOTAL_BLUE, RED_EXPECTED_HITS,
        )

        total = len(draws)
        if total < holdout + 30:
            return {"ok": False, "msg": f"数据不足: {total} < {holdout + 30}"}

        train_draws = draws[:-holdout]
        test_draws = draws[-holdout:]

        red_hits_oot = []
        blue_hits_oot = 0
        red_hits_is_baseline = []  # in-sample reference (last 20 of training)

        # Train on early data only
        oot_models = {}
        for num in range(1, 34):
            X, y = build_features(train_draws, num, is_red=True)
            if len(X) < 10:
                continue
            split = int(len(X) * 0.8)
            X_train, y_train = X[:split], y[:split]
            pos_weight = max(1, (len(y_train) - sum(y_train)) / max(1, sum(y_train)))
            model = xgb.XGBClassifier(
                n_estimators=XGB_N_ESTIMATORS, max_depth=XGB_MAX_DEPTH, learning_rate=XGB_LEARNING_RATE,
                scale_pos_weight=pos_weight, random_state=42, verbosity=0)
            model.fit(X_train, y_train)
            oot_models[f"red_{num}"] = model

        for num in range(1, 17):
            X, y = build_features(train_draws, num, is_red=False)
            if len(X) < 10:
                continue
            split = int(len(X) * 0.8)
            X_train, y_train = X[:split], y[:split]
            pos_weight = max(1, (len(y_train) - sum(y_train)) / max(1, sum(y_train)))
            model = xgb.XGBClassifier(
                n_estimators=XGB_N_ESTIMATORS, max_depth=XGB_MAX_DEPTH, learning_rate=XGB_LEARNING_RATE,
                scale_pos_weight=pos_weight, random_state=42, verbosity=0)
            model.fit(X_train, y_train)
            oot_models[f"blue_{num}"] = model

        # In-sample baseline: predict last 20 of training data
        for i in range(len(train_draws) - 20, len(train_draws)):
            window = draws[:i]
            actual = draws[i]
            red_probs = {}
            for num in range(1, 34):
                if f"red_{num}" not in oot_models:
                    red_probs[num] = 0.0
                    continue
                X_next = build_next_features(window, num, is_red=True)
                if X_next is not None:
                    red_probs[num] = float(oot_models[f"red_{num}"].predict_proba(X_next)[0][1])
            top6 = sorted(red_probs, key=lambda x: red_probs[x], reverse=True)[:6]
            actual_reds = set(actual[1:7])
            red_hits_is_baseline.append(len(set(top6) & actual_reds))

        # OOT test: predict each holdout period
        for t_idx in range(holdout):
            test_cutoff = len(train_draws) + t_idx
            window = draws[:test_cutoff]
            actual = draws[test_cutoff]
            red_probs = {}
            for num in range(1, 34):
                if f"red_{num}" not in oot_models:
                    red_probs[num] = 0.0
                    continue
                X_next = build_next_features(window, num, is_red=True)
                if X_next is not None:
                    red_probs[num] = float(oot_models[f"red_{num}"].predict_proba(X_next)[0][1])
            top6 = sorted(red_probs, key=lambda x: red_probs[x], reverse=True)[:6]
            actual_reds = set(actual[1:7])
            red_hits_oot.append(len(set(top6) & actual_reds))
            blue_probs = {}
            for num in range(1, 17):
                if f"blue_{num}" not in oot_models:
                    continue
                X_next = build_next_features(window, num, is_red=False)
                if X_next is not None:
                    blue_probs[num] = float(oot_models[f"blue_{num}"].predict_proba(X_next)[0][1])
            if blue_probs:
                top_blue = max(blue_probs, key=lambda x: blue_probs[x])
                if top_blue == actual[7]:
                    blue_hits_oot += 1

        is_mean = sum(red_hits_is_baseline) / len(red_hits_is_baseline) if red_hits_is_baseline else 0
        oot_mean = sum(red_hits_oot) / len(red_hits_oot) if red_hits_oot else 0
        random_baseline = 1.09
        oot_blue_rate = blue_hits_oot / holdout if holdout > 0 else 0

        return {
            "ok": True,
            "train_draws": len(train_draws),
            "holdout_draws": holdout,
            "is_mean_red_hit": round(is_mean, 3),
            "oot_mean_red_hit": round(oot_mean, 3),
            "oot_blue_hit_rate": round(oot_blue_rate, 3),
            "random_baseline": random_baseline,
            "oot_vs_random": round(oot_mean - random_baseline, 3),
            "delta_is_to_oot": round(is_mean - oot_mean, 3),
            "overfit_warning": (is_mean - oot_mean) > 0.3,  # in-sample beating OOT by >0.3 = overfit
            "verdict": "beats_random" if oot_mean > random_baseline + 0.1 else (
                "at_random" if abs(oot_mean - random_baseline) <= 0.1 else "below_random"),
        }


# Convenience functions
def train_xgb_models(draws, verbose=True):
    """训练 XGBoost 模型并保存到磁盘。返回训练成功的模型数量。"""
    predictor = XGBPredictor()
    if verbose:
        print(f"[XGB] Training on {len(draws)} draws...")
    n = predictor.train(draws, verbose=verbose)
    if verbose:
        print(f"[XGB] {n}/49 models trained")
    return n


def predict_xgb(draws, model_dir=None):
    """加载模型并预测下一期。"""
    predictor = XGBPredictor(model_dir=model_dir)
    predictor.load()
    if not predictor.is_trained():
        return None
    return predictor.predict(draws)
