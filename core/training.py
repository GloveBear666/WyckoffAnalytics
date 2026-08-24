# -*- coding: utf-8 -*-
"""
AI 本地训练模块 (v0.3)
======================
在用户本机基于过往真实数据训练策略:
  1. 贝叶斯优化 -> 最优参数 (最大化 Calmar/Sharpe 适应度)
  2. Walk-Forward 样本外验证 -> 准确率评估 (衰减率>30% 自动否决)
  3. 交易准确率统计: 整体胜率 + 各进场设置分项胜率
  4. 训练轮次历史 -> research/training_log.json (不断迭代, 记录最高准确率轮次)

用法(CLI): python core/training.py --symbol BTC/USDT --profile crypto --tf 4h --htf-tf 1d --trials 30
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.backtest import run_backtest
from core.data import load_data
from core.optimizer import bayesian_optimize
from core.signals import generate_signals
from validation.walk_forward import walk_forward

TRAIN_LOG = ROOT / "research" / "training_log.json"


def _accuracy_stats(trades) -> dict:
    """交易准确率统计: 整体命中率 + 分设置胜率。"""
    if not trades:
        return {"win_rate": 0.0, "trades": 0, "by_setup": {}}
    wins = [t for t in trades if t.pnl > 0]
    by_setup: dict = {}
    for t in trades:
        d = by_setup.setdefault(t.setup, {"trades": 0, "wins": 0, "pnl": 0.0})
        d["trades"] += 1
        d["wins"] += int(t.pnl > 0)
        d["pnl"] += t.pnl
    for d in by_setup.values():
        d["win_rate"] = round(d["wins"] / d["trades"], 4)
        d["pnl"] = round(d["pnl"], 2)
    return {
        "win_rate": round(len(wins) / len(trades), 4),
        "trades": len(trades),
        "by_setup": by_setup,
    }


def train_round(symbol: str, profile: str, tf: str, htf_tf: str | None = None,
                trials: int = 30, min_trades: int = 30, folds: int = 4,
                seed: int = 42) -> dict:
    """执行一轮完整训练: 优化 + 验证 + 准确率 + 历史记录。"""
    df = load_data(symbol, profile, tf)
    htf = load_data(symbol, profile, htf_tf) if htf_tf else None
    prof_name = {"crypto": "CRYPTO_PROFILE", "equity": "US_EQUITY_PROFILE"}[profile]

    # 1. 贝叶斯优化
    opt = bayesian_optimize(df, prof_name, n_trials=trials, seed=seed, htf=htf,
                            min_trades=min_trades)
    best = opt["best_params"]

    # 2. 最优参数全量回测 + 准确率
    sig = generate_signals(df, T=best["T"], feature_window=best["feature_window"], htf=htf)
    res = run_backtest(df, sig, T=best["T"], profile=prof_name,
                       max_bars_hold=best["max_bars_hold"])
    acc = _accuracy_stats(res.trades)

    # 3. Walk-Forward 验证
    wf = walk_forward(df, prof_name, n_folds=folds,
                      n_trials_per_fold=max(10, trials // 3),
                      symbol=f"{symbol} {tf}", htf=htf, min_trades=min_trades)
    wf_summary = {
        "vetoed": wf["vetoed"],
        "folds": [{
            "fold": f["fold"], "is_calmar": f["is_metrics"]["calmar"],
            "oos_calmar": f["oos_metrics"]["calmar"], "decay": f["decay_calmar"],
            "oos_trades": f["oos_metrics"]["trades"],
        } for f in wf["folds"]],
    }

    # 4. 历史记录
    round_rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "symbol": symbol, "profile": prof_name, "tf": tf, "htf_tf": htf_tf,
        "trials": trials, "seed": seed,
        "best_params": best,
        "fitness": opt["best_fitness"],
        "is_metrics": opt["metrics"],
        "accuracy": acc,
        "walk_forward": wf_summary,
    }
    if TRAIN_LOG.exists():
        log = json.loads(TRAIN_LOG.read_text(encoding="utf-8"))
    else:
        log = {"rounds": []}
    log["rounds"].append(round_rec)
    TRAIN_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    round_rec["round_id"] = len(log["rounds"])
    return round_rec


def training_history() -> dict:
    """训练历史 + 当前最优轮次。"""
    if not TRAIN_LOG.exists():
        return {"rounds": [], "best_round": None}
    log = json.loads(TRAIN_LOG.read_text(encoding="utf-8"))
    rounds = list(reversed(log["rounds"]))
    for i, r in enumerate(rounds):
        r["round_id"] = len(log["rounds"]) - i
    best = None
    for r in rounds:
        if r.get("walk_forward", {}).get("vetoed") is False:
            oos_calmar = max((f["oos_calmar"] for f in r["walk_forward"]["folds"]), default=0)
            if best is None or oos_calmar > best["best_oos_calmar"]:
                best = dict(r)
                best["best_oos_calmar"] = oos_calmar
    return {"rounds": rounds, "best_round": best}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--profile", choices=["crypto", "equity"], default="crypto")
    ap.add_argument("--tf", default="4h")
    ap.add_argument("--htf-tf", default=None)
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--min-trades", type=int, default=30)
    ap.add_argument("--folds", type=int, default=4)
    args = ap.parse_args()
    r = train_round(args.symbol, args.profile, args.tf, args.htf_tf,
                    trials=args.trials, min_trades=args.min_trades, folds=args.folds)
    print(json.dumps({k: r[k] for k in ("round_id", "best_params", "fitness", "accuracy", "walk_forward")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
