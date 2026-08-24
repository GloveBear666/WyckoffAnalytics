# -*- coding: utf-8 -*-
"""
端到端流水线: 数据 -> 温度信号 -> 摩擦回测 -> 贝叶斯优化 -> Walk-Forward 验证 -> 学习笔记
用法:
  python scripts/run_pipeline.py --symbol BTC/USDT --profile crypto --tf 1h --trials 40
  python scripts/run_pipeline.py --symbol SPY --profile equity --trials 40
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.backtest import run_backtest, print_metrics
from core.data import load_data
from core.knowledge import save_learning_note, append_strategy_log
from core.optimizer import bayesian_optimize
from core.signals import generate_signals, temperature_params, summarize_signals
from validation.walk_forward import walk_forward

PROFILE_MAP = {"crypto": "CRYPTO_PROFILE", "equity": "US_EQUITY_PROFILE"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--profile", choices=["crypto", "equity"], default="crypto")
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--htf-tf", default=None, help="高层级时间框架 (多周期确认), 如 1d/4h")
    ap.add_argument("--min-trades", type=int, default=30, help="优化器最小交易数门槛")
    ap.add_argument("--no-optimize", action="store_true")
    args = ap.parse_args()

    profile = PROFILE_MAP[args.profile]
    df = load_data(args.symbol, args.profile, args.tf)
    htf = load_data(args.symbol, args.profile, args.htf_tf) if args.htf_tf else None
    print(f"[pipeline] {args.symbol} ({profile}) bars={len(df)} "
          f"{df.index[0]} -> {df.index[-1]}"
          + (f"  HTF={args.htf_tf} ({len(htf)} bars)" if htf is not None else ""))

    # 阶段1: 温度网格基线
    print("[pipeline] phase1: temperature grid baseline (with friction)")
    grid = {}
    for T in (0.1, 0.3, 0.5, 0.7, 1.0):
        sig = generate_signals(df, T=T, htf=htf)
        res = run_backtest(df, sig, T=T, profile=profile)
        grid[f"T{T:.1f}"] = {k: res.metrics[k] for k in
                             ("total_return", "sharpe", "calmar", "max_drawdown", "trades")}
        print(f"  T={T:.1f}  {summarize_signals(sig)}")

    # 阶段2: 贝叶斯优化
    if args.no_optimize:
        opt = {"best_params": {"T": 0.5}, "metrics": grid["T0.5"], "best_fitness": 0.0}
    else:
        print(f"[pipeline] phase2: bayesian optimization ({args.trials} trials)")
        opt = bayesian_optimize(df, profile, n_trials=args.trials, htf=htf,
                                min_trades=args.min_trades)
        print(f"  best: {opt['best_params']} fitness={opt['best_fitness']:.3f}")
        print_metrics(run_backtest(df, generate_signals(df, T=opt["best_params"]["T"], htf=htf),
                                   T=opt["best_params"]["T"], profile=profile))

    # 阶段3: Walk-Forward 验证 (协议1&2)
    print(f"[pipeline] phase3: walk-forward validation ({args.folds} folds)")
    wf = walk_forward(df, profile, n_folds=args.folds, n_trials_per_fold=max(10, args.trials // 3),
                      symbol=f"{args.symbol} {args.tf}", htf=htf, min_trades=args.min_trades)
    verdict = "REJECTED (decay>30%)" if wf["vetoed"] else "PASSED"
    print(f"[pipeline] validation: {verdict}")
    for fr in wf["folds"]:
        print(f"  fold{fr['fold']}: IS calmar={fr['is_metrics']['calmar']:.2f} -> "
              f"OOS calmar={fr['oos_metrics']['calmar']:.2f} "
              f"(decay={fr['decay_calmar']*100:.0f}%)")

    # 阶段4: 学习笔记 (模块6)
    note = save_learning_note(
        topic=f"{args.symbol}_{profile}",
        decision_path=[
            "知识提取: 主教材(284页,114k字符) + 课件OCR(15页) -> 因子矩阵 v0.1 (18个基础/事件/结构因子)",
            "温度参数 T∈[0.1,1.0] 线性插值: 共振数/止损/盈亏比/仓位",
            f"贝叶斯优化 {args.trials} trials -> 最优参数 {opt['best_params']}",
            f"Walk-Forward {args.folds} 折: 验证结果 {verdict}",
        ],
        results={
            "grid": grid,
            "best_params": opt["best_params"],
            "best_fitness": opt["best_fitness"],
            "best_metrics": opt["metrics"],
            "walk_forward": {k: wf[k] for k in ("vetoed", "veto_reasons")},
        },
        failure_reasons=([f"fold{fr['fold']}: decay={fr['decay_calmar']*100:.0f}%" 
                          for fr in wf["folds"] if fr["decay_calmar"] > 0.3] or None),
        optimization_direction=[
            "若 OOS 衰减: 增加因子共振下限 / 缩小区间窗口 / 引入相对强度过滤",
            "摩擦敏感性分析: 加密配置提高滑点假设检验鲁棒性",
        ],
    )
    append_strategy_log({
        "action": "pipeline_run", "symbol": args.symbol, "profile": profile,
        "best_params": opt["best_params"], "vetoed": wf["vetoed"], "note": note.name,
    })
    print(f"[pipeline] learning note -> {note}")


if __name__ == "__main__":
    sys.exit(main())
