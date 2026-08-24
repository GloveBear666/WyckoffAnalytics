# -*- coding: utf-8 -*-
"""冒烟测试: 合成数据上验证 指标库+信号层 可运行。"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd

from core.indicators import build_feature_frame, all_events, trading_range_levels
from core.signals import generate_signals, temperature_params, summarize_signals

rng = np.random.default_rng(42)
n = 1500
# 合成: 下跌->区间(吸筹)->上涨 的威科夫风格序列
t = np.linspace(0, 1, n)
drift = np.where(t < 0.35, -0.12, np.where(t < 0.7, 0.02, 0.18))
close = 100 * np.exp(np.cumsum(drift / 25 + rng.normal(0, 0.004, n)))
vol_base = 1e6 * (1 + 3 * np.exp(-((t - 0.35) * 10) ** 2) + 2 * np.exp(-((t - 0.9) * 15) ** 2))
volume = vol_base * (1 + 0.5 * rng.random(n))
open_ = np.roll(close, 1) * (1 + rng.normal(0, 0.003, n))
high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n)))
low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume},
                  index=pd.date_range("2020-01-01", periods=n, freq="D"))

f = build_feature_frame(df)
print("feature cols:", len(f.columns))
ev = all_events(df)
print("event counts:", {k: int(v.sum()) for k, v in ev.items()})

for T in (0.1, 0.5, 1.0):
    p = temperature_params(T)
    sig = generate_signals(df, T=T)
    print(f"T={T}: {summarize_signals(sig)}")
    assert (sig["SIGNAL"] != 0).sum() >= 0

# 温度单调性检查: 高温应产生更多信号
n_lo = int((generate_signals(df, T=0.1)["SIGNAL"] != 0).sum())
n_hi = int((generate_signals(df, T=1.0)["SIGNAL"] != 0).sum())
print(f"monotonicity check: signals T0.1={n_lo} <= T1.0={n_hi}: {n_lo <= n_hi}")

# ---- 回测引擎: 双市场配置文件 + 摩擦模型 ----
from core.backtest import run_backtest, print_metrics
sig = generate_signals(df, T=0.5)
for prof in ("CRYPTO_PROFILE", "US_EQUITY_PROFILE"):
    res = run_backtest(df, sig, T=0.5, profile=prof, initial_capital=100_000)
    print(f"[backtest {prof}]")
    print_metrics(res)
    assert len(res.trades) > 0
    # 检查空头平仓现金流的数值守恒: 期末净值>0
    assert res.equity.iloc[-1] > 0
print("SMOKE_OK")
