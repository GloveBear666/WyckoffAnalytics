# -*- coding: utf-8 -*-
"""
AI_OPTIMIZATION_LAYER - 贝叶斯优化 (架构模块4)
================================================
算法: Optuna TPE (Tree-structured Parzen Estimator) 贝叶斯优化
参数空间:
  T (温度 0.1..1.0)            - 全局灵敏度
  feature_window (40..90)      - 区间结构识别窗口
  max_bars_hold (20..120)      - 时间止损
  vol_z_min (0.3..2.0)         - 量能门槛
适应度 (FITNESS_FUNCTION):
  fitness = w_calmar * tanh(calmar/2) + w_sharpe * tanh(sharpe/2) - 交易数惩罚
  默认 w_calmar=0.6, w_sharpe=0.4 (最大化卡玛比率与夏普比率)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import optuna

from core.backtest import run_backtest
from core.signals import generate_signals

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"


def _fitness(metrics: dict, w_calmar: float = 0.6, w_sharpe: float = 0.4,
             min_trades: int = 30) -> float:
    """标准化适应度: tanh 压缩 + 交易数惩罚。"""
    if metrics.get("trades", 0) < min_trades:
        return -1.0
    calmar = max(metrics["calmar"], -5.0)
    sharpe = max(metrics["sharpe"], -5.0)
    f = w_calmar * np.tanh(calmar / 2.0) + w_sharpe * np.tanh(sharpe / 2.0)
    # 交易数过少惩罚
    if metrics["trades"] < min_trades * 1.5:
        f *= metrics["trades"] / (min_trades * 1.5)
    return float(f)


def objective_factory(df: pd.DataFrame, profile: str,
                      fixed: dict | None = None, htf: pd.DataFrame | None = None,
                      min_trades: int = 30):
    def objective(trial: optuna.Trial) -> float:
        T = trial.suggest_float("T", 0.1, 1.0)
        fw = trial.suggest_int("feature_window", 40, 90, step=5)
        mh = trial.suggest_int("max_bars_hold", 20, 120, step=10)
        vz = trial.suggest_float("vol_z_min", 0.3, 2.0)
        if fixed:
            for k, v in fixed.items():
                if k == "T": T = v
                elif k == "feature_window": fw = v
                elif k == "max_bars_hold": mh = v
                elif k == "vol_z_min": vz = v
        sig = generate_signals(df, T=T, feature_window=fw, htf=htf)
        res = run_backtest(df, sig, T=T, profile=profile, max_bars_hold=mh)
        return _fitness(res.metrics, min_trades=min_trades)
    return objective


def bayesian_optimize(df: pd.DataFrame, profile: str, n_trials: int = 60,
                      seed: int = 42, study_name: str = "wyckoff_bayes",
                      htf: pd.DataFrame | None = None, min_trades: int = 30) -> dict:
    """运行贝叶斯优化, 返回最优参数+指标。"""
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=seed),
                                study_name=study_name)
    study.optimize(objective_factory(df, profile, htf=htf, min_trades=min_trades),
                   n_trials=n_trials)

    best = study.best_params
    sig = generate_signals(df, T=best["T"], feature_window=best["feature_window"], htf=htf)
    res = run_backtest(df, sig, T=best["T"], profile=profile,
                       max_bars_hold=best["max_bars_hold"])
    return {
        "best_params": best,
        "best_fitness": float(study.best_value),
        "metrics": res.metrics,
        "n_trials": n_trials,
    }


if __name__ == "__main__":
    from core.data import load_data
    result = bayesian_optimize(load_data("BTC/USDT", "crypto", "1h"), "CRYPTO_PROFILE")
    print(json.dumps(result, ensure_ascii=False, indent=2))
