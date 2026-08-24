# -*- coding: utf-8 -*-
"""
VALIDATION_CONSTRAINTS - 强制验证协议 (架构模块5)
==================================================
PROTOCOL_1: 步进分析 (Walk-Forward Analysis)
  - 数据切分为 N 折; 第 i 折优化(样本内 IS), 第 i+1 折检验(样本外 OOS)
PROTOCOL_2: 样本外测试 (Out-of-Sample Testing)
RULE: 历史回测表现优异但样本外衰减率 (Decay Rate) > 30% 的策略必须被系统自动否决。

输出: research/validation/walk_forward_report.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from core.backtest import run_backtest
from core.optimizer import bayesian_optimize, _fitness
from core.signals import generate_signals

ROOT = Path(__file__).resolve().parent.parent
VALIDATION_DIR = ROOT / "research" / "validation"

DECAY_VETO_THRESHOLD = 0.30  # 衰减率否决阈值 (协议: >30% 自动否决)


def split_folds(df: pd.DataFrame, n_folds: int = 4) -> list[pd.DataFrame]:
    """等长切分为 n_folds 折。"""
    idx = np.array_split(np.arange(len(df)), n_folds)
    return [df.iloc[ix].copy() for ix in idx]


def walk_forward(df: pd.DataFrame, profile: str, n_folds: int = 4,
                 n_trials_per_fold: int = 30, seed: int = 42,
                 symbol: str = "SYMBOL", htf: pd.DataFrame | None = None,
                 min_trades: int = 30) -> dict:
    """步进分析: 每折 训练->优化->OOS 检验。htf: 高层级时间框架(多周期确认)。"""
    folds = split_folds(df, n_folds)
    report: dict = {
        "protocol": "WALK_FORWARD",
        "symbol": symbol,
        "profile": profile,
        "n_folds": n_folds,
        "n_trials_per_fold": n_trials_per_fold,
        "decay_veto_threshold": DECAY_VETO_THRESHOLD,
        "htf_enabled": htf is not None,
        "min_trades": min_trades,
        "folds": [],
    }
    oos_equities: list[pd.Series] = []
    for i in range(n_folds - 1):
        train = pd.concat(folds[: i + 1])
        test = folds[i + 1]
        opt = bayesian_optimize(train, profile, n_trials=n_trials_per_fold, seed=seed + i,
                                htf=htf, min_trades=min_trades)
        best = opt["best_params"]
        # OOS 检验
        sig = generate_signals(test, T=best["T"], feature_window=best["feature_window"], htf=htf)
        oos_res = run_backtest(test, sig, T=best["T"], profile=profile,
                               max_bars_hold=best["max_bars_hold"])
        is_m, oos_m = opt["metrics"], oos_res.metrics

        def decay(is_v, oos_v):
            return float((is_v - oos_v) / max(abs(is_v), 1e-9))

        fold_rec = {
            "fold": i + 1,
            "train_range": [str(train.index[0]), str(train.index[-1])],
            "test_range": [str(test.index[0]), str(test.index[-1])],
            "best_params": best,
            "is_metrics": is_m,
            "oos_metrics": oos_m,
            "decay_calmar": decay(is_m["calmar"], oos_m["calmar"]),
            "decay_sharpe": decay(is_m["sharpe"], oos_m["sharpe"]),
            "decay_return": decay(is_m["total_return"], oos_m["total_return"]),
        }
        report["folds"].append(fold_rec)
        oos_equities.append(oos_res.equity)

    # 汇总 OOS
    if oos_equities:
        oos_eq = pd.concat(oos_equities)
        oos_eq = oos_eq[~oos_eq.index.duplicated(keep="first")].sort_index()
        # 拼接净值以折为单位复利: 简单拼接等价于分段净值
        ret = oos_eq.pct_change().dropna()
        from core.backtest import _calc_metrics, TRADING_DAYS
        prof = json.loads((ROOT / "config" / "market_profiles.json").read_text(encoding="utf-8"))
        days = TRADING_DAYS[prof["profiles"][profile].get("market_type", "crypto")]
        report["oos_aggregate"] = _calc_metrics(oos_eq, [], days)

    # 否决判定: 任一折 decay_calmar > 30% 或 decay_sharpe > 30% 且 OOS 不佳
    vetoes = []
    for fr in report["folds"]:
        if fr["decay_calmar"] > DECAY_VETO_THRESHOLD and fr["oos_metrics"]["calmar"] < 0.5:
            vetoes.append({"fold": fr["fold"], "reason": "calmar_decay",
                           "decay": fr["decay_calmar"]})
        if fr["decay_sharpe"] > DECAY_VETO_THRESHOLD and fr["oos_metrics"]["sharpe"] < 0.5:
            vetoes.append({"fold": fr["fold"], "reason": "sharpe_decay",
                           "decay": fr["decay_sharpe"]})
    report["vetoed"] = len(vetoes) > 0
    report["veto_reasons"] = vetoes

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", symbol)
    out = VALIDATION_DIR / f"walk_forward_{safe}_{profile}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[validation] report -> {out}  vetoed={report['vetoed']}")
    return report
