# -*- coding: utf-8 -*-
"""生成 SPY (通过验证策略) 净值曲线与回撤图。"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.plotutils import setup_chinese_font

setup_chinese_font()

from core.backtest import run_backtest
from core.data import load_data
from core.signals import generate_signals

df = load_data("SPY", "equity", "1d")
best = {"T": 0.189810768175771, "feature_window": 75, "max_bars_hold": 70}
sig = generate_signals(df, T=best["T"], feature_window=best["feature_window"])
res = run_backtest(df, sig, T=best["T"], profile="US_EQUITY_PROFILE",
                   max_bars_hold=best["max_bars_hold"])

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
ax1.plot(res.equity.index, res.equity.values / 1e5, lw=1.2, color="#1f77b4")
ax1.set_title("SPY - Wyckoff 策略净值曲线 (T=0.19, 摩擦后, Walk-Forward PASSED)")
ax1.set_ylabel("净值倍数")
ax1.grid(alpha=0.3)
dd = res.equity / res.equity.cummax() - 1
ax2.fill_between(dd.index, dd.values * 100, 0, color="#d62728", alpha=0.5)
ax2.set_ylabel("回撤 %")
ax2.grid(alpha=0.3)
m = res.metrics
ax1.text(0.01, 0.97,
         f"收益 {m['total_return']*100:.1f}% | Sharpe {m['sharpe']:.2f} | Calmar {m['calmar']:.2f} | "
         f"MaxDD {m['max_drawdown']*100:.2f}% | 胜率 {m['win_rate']*100:.0f}% | {m['trades']}笔",
         transform=ax1.transAxes, va="top", fontsize=9,
         bbox=dict(boxstyle="round", fc="white", alpha=0.8))
plt.tight_layout()
out = Path("research/backtests/SPY_equity_curve.png")
out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, dpi=150)
print(f"[chart] -> {out}")
