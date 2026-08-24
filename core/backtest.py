# -*- coding: utf-8 -*-
"""
EXECUTION_ENGINE - 回测引擎 + 摩擦模型 (架构模块4)
====================================================
执行规则:
  - 信号在 bar t 收盘产生, bar t+1 开盘成交 (无前视)
  - 多头: 买 open*(1+slip+half_spread), 卖 价格*(1-slip-half_spread)
  - 止损/止盈/时间止损在盘中以 bar 高低价判定 (保守: 止损优先)
  - 摩擦: taker 费率 + 滑点 + 买卖价差 (配置来自 market_profiles.json)
绩效指标: CAGR, Sharpe, Sortino, Calmar, MaxDD, 胜率, 盈亏比, Profit Factor
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from core.signals import temperature_params

ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = ROOT / "config" / "market_profiles.json"

TRADING_DAYS = {"crypto": 365, "equity": 252}


@dataclass
class Trade:
    entry_dt: pd.Timestamp
    exit_dt: pd.Timestamp
    direction: int
    setup: str
    entry: float
    exit: float
    shares: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    bars_held: int
    entry_idx: int = 0


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: list[Trade]
    metrics: dict
    params: dict = field(default_factory=dict)


def load_profile(profile: str) -> dict:
    cfg = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return cfg["profiles"][profile]


def _apply_friction(price: float, side: str, profile: dict) -> float:
    """side: 'buy'|'sell'. 返回含摩擦的实际成交价。"""
    slip = profile["execution"]["slippage_bps"] / 1e4
    spread = profile["execution"]["spread_bps"] / 1e4 / 2  # 半价差
    fee = profile["execution"]["fee_rate_taker_bps"] / 1e4
    if side == "buy":
        return price * (1 + slip + spread) * (1 + fee)
    return price * (1 - slip - spread) * (1 - fee)


def _calc_metrics(equity: pd.Series, trades: list[Trade], days_per_year: int) -> dict:
    if len(equity) < 2:
        return {"error": "equity too short"}
    ret = equity.pct_change().dropna()
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = max(len(equity) / days_per_year, 1 / days_per_year)
    cagr = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1.0
    vol = ret.std() * np.sqrt(days_per_year)
    sharpe = (ret.mean() / ret.std() * np.sqrt(days_per_year)) if ret.std() > 0 else 0.0
    downside = ret[ret < 0].std() * np.sqrt(days_per_year)
    sortino = (ret.mean() / downside * np.sqrt(days_per_year)) if downside > 0 else 0.0
    cummax = equity.cummax()
    dd = equity / cummax - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else 0.0

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gross_win = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    win_rate = len(wins) / len(trades) if trades else 0.0
    profit_factor = gross_win / gross_loss if gross_loss > 0 else (np.inf if gross_win > 0 else 0.0)
    avg_hold = float(np.mean([t.bars_held for t in trades])) if trades else 0.0

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "volatility": float(vol),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_dd),
        "calmar": float(calmar),
        "trades": len(trades),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "avg_bars_held": float(avg_hold),
        "gross_profit": float(gross_win),
        "gross_loss": float(gross_loss),
    }


def run_backtest(df: pd.DataFrame, signals: pd.DataFrame, T: float = 0.5,
                 profile: str = "CRYPTO_PROFILE", initial_capital: float = 100_000.0,
                 max_bars_hold: int = 60, entry_cooldown: int = 5) -> BacktestResult:
    """核心回测循环。df/signals 索引须对齐。
    entry_cooldown: 同方向入场冷却K线数 (避免连续信号重复开仓)。"""
    prof = load_profile(profile)
    p = temperature_params(T)
    days_per_year = TRADING_DAYS[prof.get("market_type", "crypto")]

    pos_pct = p["risk.position_pct"]
    max_positions = int(p["risk.max_positions"])
    daily_loss_limit = p["risk.daily_loss_limit_pct"] / 100.0

    equity = initial_capital
    eq_curve: list[float] = []
    cash = initial_capital
    positions: list[dict] = []  # 活跃持仓
    trades: list[Trade] = []
    day_pnl = 0.0
    last_day = None

    def close_position(pos: dict, dt, price, reason, idx) -> None:
        nonlocal cash
        slip_price = _apply_friction(price, "sell" if pos["dir"] == 1 else "buy", prof)
        if pos["dir"] == 1:  # 多头: 卖出回款
            cash += slip_price * pos["shares"]
            gross = (slip_price - pos["entry_filled"]) * pos["shares"]
        else:  # 空头: 买回归还
            cash -= slip_price * pos["shares"]
            gross = (pos["entry_filled"] - slip_price) * pos["shares"]
        trades.append(Trade(
            entry_dt=pos["entry_dt"], exit_dt=dt, direction=pos["dir"], setup=pos["setup"],
            entry=pos["entry_filled"], exit=slip_price, shares=pos["shares"],
            pnl=gross, pnl_pct=gross / pos["entry_cost"], exit_reason=reason,
            bars_held=idx - pos["entry_idx"], entry_idx=pos["entry_idx"]))
        positions.remove(pos)

    for idx, (dt, row) in enumerate(df.iterrows()):
        sig = signals.loc[dt]
        if last_day is not None and dt.date() != last_day:
            day_pnl = 0.0  # 日亏损熔断重置
        last_day = dt.date()

        # ---- 1. 先处理退出 (stop/target 用当日高低价判定, 保守: 止损优先) ----
        for pos in list(positions):
            o, h, l = row["open"], row["high"], row["low"]
            if pos["dir"] == 1:
                if l <= pos["stop"]:
                    close_position(pos, dt, pos["stop"], "stop", idx)
                elif h >= pos["target"]:
                    close_position(pos, dt, pos["target"], "target", idx)
            else:
                if h >= pos["stop"]:
                    close_position(pos, dt, pos["stop"], "stop", idx)
                elif l <= pos["target"]:
                    close_position(pos, dt, pos["target"], "target", idx)
            # 时间止损
            if pos in positions and idx - pos["entry_idx"] >= max_bars_hold:
                close_position(pos, dt, row["close"], "time", idx)

        # ---- 2. 日亏损熔断 (当日亏损超阈值则禁止开新仓) ----
        if day_pnl <= -daily_loss_limit * initial_capital:
            eq_curve.append(cash + sum(pos["shares"] * row["close"] * pos["dir"] for pos in positions))
            continue  # 熔断日不再开新仓

        # ---- 3. 新开仓 (t+1 开盘执行) ----
        if sig["SIGNAL"] != 0 and len(positions) < max_positions:
            dir_ = int(sig["SIGNAL"])

            def _skip_entry(reason: str) -> None:
                """跳过滤(跳空/冷却): 记账后跳过本bar入场。"""
                nonlocal equity, day_pnl
                mtm_skip = cash + sum(pp["shares"] * row["close"] * pp["dir"] for pp in positions)
                eq_curve.append(mtm_skip)
                day_pnl += mtm_skip - (eq_curve[-2] if len(eq_curve) > 1 else initial_capital)
                equity = mtm_skip

            # 跳空缺口过滤 (US_EQUITY_PROFILE 微结构): 隔夜跳空 > mult*ATR 跳过入场
            gap_mult = prof.get("microstructure", {}).get("gap_filter_mult")
            if gap_mult and idx > 0:
                prev_close = df["close"].iloc[idx - 1]
                if prev_close > 0:
                    gap_pct = abs(row["open"] / prev_close - 1)
                    if gap_pct > gap_mult * (sig["ATR"] / prev_close):
                        _skip_entry("gap_filter")
                        continue
            # 同方向入场冷却
            if trades and any(abs(idx - t.entry_idx) < entry_cooldown for t in trades if t.direction == dir_):
                _skip_entry("cooldown")
                continue

            entry_ref = row["open"]  # t+1 开盘
            a = sig["ATR"]
            entry_filled = _apply_friction(entry_ref, "buy" if dir_ == 1 else "sell", prof)
            budget = min(pos_pct * equity, cash if dir_ == 1 else equity)
            if budget > 0:
                shares = budget / entry_filled
                stop_dist = p["risk.stop_atr_mult"] * a
                stop = entry_ref - stop_dist if dir_ == 1 else entry_ref + stop_dist
                risk_amt = p["risk.take_profit_rr"] * stop_dist
                target = entry_ref + risk_amt if dir_ == 1 else entry_ref - risk_amt
                positions.append({
                    "dir": dir_, "setup": sig["SETUP"], "shares": shares,
                    "entry_filled": entry_filled, "entry_cost": shares * entry_filled,
                    "stop": stop, "target": target, "entry_dt": dt, "entry_idx": idx})
                if dir_ == 1:
                    cash -= shares * entry_filled  # 多头: 支付买入款
                else:
                    cash += shares * entry_filled  # 空头: 收到卖出所得(买回时归还)

        # ---- 4. 净值记账 (以当日收盘计) ----
        mtm = cash + sum(pos["shares"] * row["close"] * pos["dir"] for pos in positions)
        equity = mtm
        day_pnl += mtm - (eq_curve[-1] if eq_curve else initial_capital)
        eq_curve.append(mtm)

    # 期末强制平仓
    if positions:
        last_dt = df.index[-1]
        last_row = df.iloc[-1]
        for pos in list(positions):
            close_position(pos, last_dt, last_row["close"], "end_of_data", len(df) - 1)
        mtm = cash
        eq_curve[-1] = mtm

    equity_s = pd.Series(eq_curve, index=df.index, dtype=float)
    metrics = _calc_metrics(equity_s, trades, days_per_year)
    return BacktestResult(equity=equity_s, trades=trades, metrics=metrics,
                          params={"T": T, "profile": profile, "initial_capital": initial_capital})


def print_metrics(res: BacktestResult) -> None:
    m = res.metrics
    print(f"  T={res.params['T']}  profile={res.params['profile']}")
    print(f"    return={m['total_return']*100:7.2f}%  CAGR={m['cagr']*100:6.2f}%  "
          f"Sharpe={m['sharpe']:5.2f}  Sortino={m['sortino']:5.2f}  Calmar={m['calmar']:5.2f}")
    print(f"    MaxDD={m['max_drawdown']*100:6.2f}%  trades={m['trades']:4d}  "
          f"winrate={m['win_rate']*100:5.1f}%  PF={m['profit_factor']:5.2f}")
