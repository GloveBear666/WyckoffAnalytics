# -*- coding: utf-8 -*-
"""
EXECUTION_ENGINE - 威科夫量化指标库 (架构模块3)
================================================
因子实现对应 knowledge/factors/factor_matrix_v0.1.json 中的 ID:
  F_VOL_Z, F_RANGE_PCT, F_BODY_RATIO, F_UPPER_WICK, F_LOWER_WICK,
  F_CLOSE_POS, F_UPVOL_RATIO, F_ROC, F_EFFORT_RESULT, F_RISK_ATR,
  EVT_* 事件, F_*_SCORE 结构评分

全部因子仅使用 价格/成交量/走势速度 三要素 (威科夫原则, 书p18)。
输入 DataFrame 必须含列: open, high, low, close, volume (datetime索引)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-9


# --------------------------------------------------------------------------
# 基础量价因子 (base_pv)
# --------------------------------------------------------------------------
def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """F_RISK_ATR: 平均真实波幅。"""
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def volume_zscore(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """F_VOL_Z: 成交量Z分数。"""
    v = df["volume"]
    mean = v.rolling(n, min_periods=max(3, n // 2)).mean()
    std = v.rolling(n, min_periods=max(3, n // 2)).std()
    return (v - mean) / (std + EPS)


def range_pct(df: pd.DataFrame) -> pd.Series:
    """F_RANGE_PCT: 振幅百分比 (high-low)/close。"""
    return (df["high"] - df["low"]) / (df["close"] + EPS) * 100.0


def body_ratio(df: pd.DataFrame) -> pd.Series:
    """F_BODY_RATIO: 实体占比。"""
    rng = (df["high"] - df["low"]).abs()
    return (df["close"] - df["open"]).abs() / (rng + EPS)


def upper_wick(df: pd.DataFrame) -> pd.Series:
    """F_UPPER_WICK: 上影线占比。"""
    rng = (df["high"] - df["low"]).abs()
    return (df["high"] - df[["open", "close"]].max(axis=1)) / (rng + EPS)


def lower_wick(df: pd.DataFrame) -> pd.Series:
    """F_LOWER_WICK: 下影线占比。"""
    rng = (df["high"] - df["low"]).abs()
    return (df[["open", "close"]].min(axis=1) - df["low"]) / (rng + EPS)


def close_pos(df: pd.DataFrame) -> pd.Series:
    """F_CLOSE_POS: 收盘位置 0..1。"""
    rng = (df["high"] - df["low"]).abs()
    return (df["close"] - df["low"]) / (rng + EPS)


def upvol_ratio(df: pd.DataFrame, n: int = 10) -> pd.Series:
    """F_UPVOL_RATIO: 阳线成交量占比。"""
    up_vol = df["volume"].where(df["close"] >= df["open"], 0.0)
    return up_vol.rolling(n, min_periods=3).sum() / (df["volume"].rolling(n, min_periods=3).sum() + EPS)


def roc(df: pd.DataFrame, n: int = 5) -> pd.Series:
    """F_ROC: 走势速度。"""
    return df["close"].pct_change(n) * 100.0


def effort_result(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """F_EFFORT_RESULT: 努力结果比 = 量能Z / 价格变动幅度。
    高值 = 量增价滞 = 停止行为 (书p25,p44)。"""
    z = volume_zscore(df, n)
    pct_move = df["close"].pct_change().abs() * 100.0
    return z / (pct_move + EPS)


# --------------------------------------------------------------------------
# 结构因子 (structure)
# --------------------------------------------------------------------------
def trading_range_levels(df: pd.DataFrame, window: int = 60, q_hi: float = 0.90,
                         q_lo: float = 0.10) -> pd.DataFrame:
    """F_TR_LEVELS: 滚动区间支撑/阻力。
    上边界=窗口内高点分位+量加权; 下边界=低点分位。量加权提高密集成交区权重。"""
    v = df["volume"]
    vw = v / (v.rolling(window, min_periods=20).sum() + EPS)
    hi = (df["high"] * vw).rolling(window, min_periods=20).quantile(q_hi) / (
        vw.rolling(window, min_periods=20).quantile(q_hi) + EPS)
    lo = (df["low"] * vw).rolling(window, min_periods=20).quantile(q_lo) / (
        vw.rolling(window, min_periods=20).quantile(q_lo) + EPS)
    return pd.DataFrame({"resistance": hi, "support": lo})


def supply_exhaustion(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """F_SUPPLY_EXHAUST: 供应枯竭度 = 最近回调波量 / 前期回调波量 (越低越枯竭)。
    简化: 当前回落段(阴线)均量 / 前n日阴线均量。"""
    bearish = df["close"] < df["open"]
    v = df["volume"]
    cur = v.where(bearish).rolling(5, min_periods=2).mean()
    prev = v.where(bearish).shift(5).rolling(20, min_periods=10).mean()
    return cur / (prev + EPS)


def demand_growth(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """F_DEMAND_GROWTH: 需求增长率 = 阳线量价斜率。
    上涨波中 量增价涨 → 需求持续扩大 (书p42,p73)。"""
    bullish = df["close"] >= df["open"]
    up_vol = df["volume"].where(bullish, np.nan).rolling(n, min_periods=8).sum()
    up_range = df["high"].where(bullish, np.nan).rolling(n, min_periods=8).sum() - \
        df["low"].where(bullish, np.nan).rolling(n, min_periods=8).sum()
    slope = (up_vol.diff() / (up_range.diff() + EPS)).fillna(0.0)
    return slope.clip(-1, 1)


def regime(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.DataFrame:
    """F_REGIME: 趋势环境质量。返回 (regime_code, quality).
    code: 1=牛市(价>慢均线且快均线上行), -1=熊市(价<慢均线且快均线下行), 0=区间。
    quality: 量价协调度 0..1 = 阳线放量阴线缩量的比例。"""
    c = df["close"]
    ma_f, ma_s = c.rolling(fast, min_periods=fast // 2).mean(), c.rolling(slow, min_periods=slow // 2).mean()
    slope_f = ma_f.diff(5)
    up_ok = (c > ma_s) & (slope_f > 0)
    dn_ok = (c < ma_s) & (slope_f < 0)
    code = np.where(up_ok, 1, np.where(dn_ok, -1, 0))
    # 量价协调: 阳线量>阴线量 → 协调
    up_v = df["volume"].where(df["close"] >= df["open"], np.nan)
    dn_v = df["volume"].where(df["close"] < df["open"], np.nan)
    coord = (up_v.rolling(20, min_periods=10).mean() /
             (dn_v.rolling(20, min_periods=10).mean() + EPS))
    quality = (coord / (1 + coord)).clip(0, 1).fillna(0.5)
    return pd.DataFrame({"regime": code, "quality": quality})


def accumulation_score(df: pd.DataFrame) -> pd.Series:
    """F_RANGE_ACCUM_SCORE: 吸筹评分 0..1。
    天量抛售→低量测底→震仓→长阳带量离开 (书p30); 上涨量增下跌量减 (p73)。"""
    vol_z = volume_zscore(df)
    rng = range_pct(df)
    body = body_ratio(df)
    up_vol = df["volume"].where(df["close"] >= df["open"], np.nan)
    dn_vol = df["volume"].where(df["close"] < df["open"], np.nan)
    absorb = (up_vol.rolling(20, min_periods=10).mean() /
              (dn_vol.rolling(20, min_periods=10).mean() + EPS))
    score = (absorb / (1 + absorb)).clip(0, 1)
    # 震仓回收加分: 深跌后快速收回
    lo_min = df["low"].rolling(30, min_periods=15).min()
    bounce = (df["close"] > df["low"].shift(1).rolling(5, min_periods=3).min() * 0.97).astype(float)
    return ((score * 0.7 + bounce * 0.3) * vol_z.rolling(5).mean().clip(0, 2).fillna(0.5) / 2 + 0.25).clip(0, 1)


def distribution_score(df: pd.DataFrame) -> pd.Series:
    """F_RANGE_DIST_SCORE: 派发评分 0..1。
    顶部放量长上影 + 上涨量递减(需求枯竭) + 下跌量递增 (p26,p29)。"""
    upper = upper_wick(df)
    up_vol = df["volume"].where(df["close"] >= df["open"], np.nan)
    dn_vol = df["volume"].where(df["close"] < df["open"], np.nan)
    up_decay = 1 - (up_vol.rolling(10, min_periods=5).mean() /
                    (up_vol.shift(10).rolling(10, min_periods=5).mean() + EPS))
    dn_growth = (dn_vol.rolling(10, min_periods=5).mean() /
                 (up_vol.rolling(10, min_periods=5).mean() + EPS))
    wick_comp = upper.rolling(5, min_periods=3).max()
    return ((wick_comp * 0.4 + up_decay.clip(0, 1) * 0.3 + (dn_growth / (1 + dn_growth)).clip(0, 1) * 0.3)
            .fillna(0.3).clip(0, 1))


# --------------------------------------------------------------------------
# 事件因子 (events) - 全部返回 bool Series
# --------------------------------------------------------------------------
def selling_climax(df: pd.DataFrame, n: int = 20, vol_z_th: float = 2.0) -> pd.Series:
    """EVT_SC: 恐慌抛售 = 下跌背景 + 天量 + 极宽振幅 + 阴线。"""
    bear = df["close"] < df["close"].rolling(50, min_periods=25).mean()
    big_vol = volume_zscore(df, n) > vol_z_th
    wide = range_pct(df) > range_pct(df).rolling(100, min_periods=50).quantile(0.95)
    bearish = df["close"] < df["open"]
    return (bear & big_vol & wide & bearish).fillna(False)


def buying_climax(df: pd.DataFrame, n: int = 20, vol_z_th: float = 2.0) -> pd.Series:
    """EVT_BC: 抢购高潮 = 上涨背景 + 天量 + 超长阳线。"""
    bull = df["close"] > df["close"].rolling(50, min_periods=25).mean()
    big_vol = volume_zscore(df, n) > vol_z_th
    wide = range_pct(df) > range_pct(df).rolling(100, min_periods=50).quantile(0.95)
    bullish = df["close"] >= df["open"]
    return (bull & big_vol & wide & bullish).fillna(False)


def secondary_test(df: pd.DataFrame, lookback: int = 40) -> pd.Series:
    """EVT_ST: 成功二次测试 = 价格接近区间低点(回测SC区) + 低量 + 小振幅。
    测试蜡烛必须小蜡烛+低量=供应枯竭 (书p32,p41,p68)。"""
    close = df["close"]
    vol_z = volume_zscore(df)
    lo_min = df["low"].rolling(lookback, min_periods=20).min()
    near_low = close <= lo_min * 1.03
    low_vol = vol_z < 0.0
    rng = range_pct(df)
    small_range = rng < rng.rolling(50, min_periods=25).median() * 0.6
    return (near_low & low_vol & small_range).fillna(False)


def spring(df: pd.DataFrame, levels: pd.DataFrame, lookback: int = 3,
           depth_pct: float = 1.5) -> pd.Series:
    """EVT_SPRING: 下冲反弹 = 价格跌破支撑(≤depth%)后 3 根内收回支撑上。
    轻微突破直接进场; 大幅突破+增量等ST (书p74)。"""
    sup = levels["support"]
    pierce = df["low"] < sup * (1 - depth_pct / 100)
    recover = df["close"] > sup
    # 收回需发生在突破后的 lookback 根内: 用移位窗口
    rec_soon = recover | recover.shift(-1) | recover.shift(-2) | recover.shift(-3)
    valid = (pierce & rec_soon).fillna(False)
    # 深度突破(>3*ATR)需二次测试: 事件仍标记, 由信号层降权
    return valid


def upthrust(df: pd.DataFrame, levels: pd.DataFrame, lookback: int = 3,
             depth_pct: float = 1.5) -> pd.Series:
    """EVT_UT: 上冲回落 = 价格上破阻力后 3 根内收回阻力下 (上影线形态)。
    需阴线跟随+量递增才有效 (书p39,p60)。"""
    res = levels["resistance"]
    pierce = df["high"] > res * (1 + depth_pct / 100)
    fall = df["close"] < res
    fall_soon = fall | fall.shift(-1) | fall.shift(-2) | fall.shift(-3)
    vol_rising = df["volume"] > df["volume"].rolling(10, min_periods=5).mean()
    bear_follow = (df["close"] < df["open"]) | (df["close"].shift(-1) < df["open"].shift(-1))
    return (pierce & fall_soon & vol_rising & bear_follow).fillna(False)


def sos(df: pd.DataFrame, levels: pd.DataFrame, n: int = 20, vol_z_th: float = 1.5) -> pd.Series:
    """EVT_SOS: 强势出现 = 放量宽幅阳线突破区间上边界 (书p60-61)。"""
    res = levels["resistance"]
    breakout = df["close"] > res
    big_vol = volume_zscore(df, n) > vol_z_th
    wide = range_pct(df) > range_pct(df).rolling(100, min_periods=50).quantile(0.8)
    bullish = df["close"] >= df["open"]
    return (breakout & big_vol & wide & bullish).fillna(False)


def sow(df: pd.DataFrame, levels: pd.DataFrame, n: int = 20, vol_z_th: float = 1.5) -> pd.Series:
    """EVT_SOW: 弱势出现 = 放量宽幅阴线跌破区间下边界 (书p52,p61)。"""
    sup = levels["support"]
    breakdown = df["close"] < sup
    big_vol = volume_zscore(df, n) > vol_z_th
    wide = range_pct(df) > range_pct(df).rolling(100, min_periods=50).quantile(0.8)
    bearish = df["close"] < df["open"]
    return (breakdown & big_vol & wide & bearish).fillna(False)


def joc(df: pd.DataFrame, levels: pd.DataFrame, n: int = 20, vol_z_th: float = 2.0) -> pd.Series:
    """EVT_JOC: 跃过小溪 = 强烈上涨突破关键阻力, 高量宽幅 (书p60)。"""
    res = levels["resistance"]
    breakout = df["close"] > res.shift(1)
    big_vol = volume_zscore(df, n) > vol_z_th
    wide = range_pct(df) > range_pct(df).rolling(100, min_periods=50).quantile(0.9)
    return (breakout & big_vol & wide).fillna(False)


def shakeout(df: pd.DataFrame, n: int = 5, depth_atr: float = 2.0) -> pd.Series:
    """EVT_SHAKEOUT: 震仓 = 突发深跌(>2*ATR)后 n 根内收回 (书p59)。
    终极震仓 = 深度更大(>3*ATR)且放量。"""
    a = atr(df)
    lo_min = df["low"].rolling(30, min_periods=15).min()
    drop = (lo_min.shift(1) - df["low"]) > depth_atr * a
    rec = (df["close"] > lo_min.shift(1))
    rec_soon = rec | rec.shift(-1) | rec.shift(-2) | rec.shift(-3) | rec.shift(-4)
    return (drop & rec_soon).fillna(False)


def stop_action(df: pd.DataFrame, levels: pd.DataFrame) -> pd.Series:
    """EVT_STOP_ACTION: 停止行为 = 支撑附近 窄幅 + 量不缩 (努力无结果, 书p23,p25,p34)。"""
    sup = levels["support"]
    near_sup = df["low"] <= sup * 1.02
    narrow = body_ratio(df) < 0.3
    vol_not_shrink = df["volume"] >= df["volume"].rolling(10, min_periods=5).mean() * 0.9
    return (near_sup & narrow & vol_not_shrink).fillna(False)


def dead_point(df: pd.DataFrame, k: int = 5) -> pd.Series:
    """EVT_DEAD_POINT: 死角 = 高点降低+低点升高+ATR连续收缩 (书p23,p59)。"""
    hh = df["high"].rolling(k, min_periods=k).max()
    ll = df["low"].rolling(k, min_periods=k).min()
    lower_highs = df["high"].shift(1).rolling(k - 1, min_periods=k - 1).max() < hh.shift(k)
    higher_lows = df["low"].shift(1).rolling(k - 1, min_periods=k - 1).min() > ll.shift(k)
    a = atr(df)
    atr_shrink = a < a.shift(1).rolling(k, min_periods=k).mean()
    squeeze = (hh - ll) < (df["high"] - df["low"]).rolling(50, min_periods=25).quantile(0.3)
    return (lower_highs & higher_lows & atr_shrink & squeeze).fillna(False)


def all_events(df: pd.DataFrame, levels: pd.DataFrame | None = None) -> pd.DataFrame:
    """汇总全部事件为一张表。"""
    lv = levels if levels is not None else trading_range_levels(df)
    return pd.DataFrame({
        "EVT_SC": selling_climax(df),
        "EVT_BC": buying_climax(df),
        "EVT_ST": secondary_test(df),
        "EVT_SPRING": spring(df, lv),
        "EVT_UT": upthrust(df, lv),
        "EVT_SOS": sos(df, lv),
        "EVT_SOW": sow(df, lv),
        "EVT_JOC": joc(df, lv),
        "EVT_SHAKEOUT": shakeout(df),
        "EVT_STOP_ACTION": stop_action(df, lv),
        "EVT_DEAD_POINT": dead_point(df),
    })


def build_feature_frame(df: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """构造完整特征帧: 基础因子 + 结构 + 事件 (供信号层/优化层使用)。"""
    out = df[["open", "high", "low", "close", "volume"]].copy()
    out["ATR"] = atr(df)
    out["VOL_Z"] = volume_zscore(df)
    out["RANGE_PCT"] = range_pct(df)
    out["BODY_RATIO"] = body_ratio(df)
    out["UPPER_WICK"] = upper_wick(df)
    out["LOWER_WICK"] = lower_wick(df)
    out["CLOSE_POS"] = close_pos(df)
    out["UPVOL_RATIO"] = upvol_ratio(df)
    out["ROC"] = roc(df)
    out["EFFORT_RESULT"] = effort_result(df)
    lv = trading_range_levels(df, window=window)
    out["SUPPORT"] = lv["support"]
    out["RESISTANCE"] = lv["resistance"]
    out["SUPPLY_EXHAUST"] = supply_exhaustion(df)
    out["DEMAND_GROWTH"] = demand_growth(df)
    rg = regime(df)
    out["REGIME"] = rg["regime"]
    out["REGIME_QUALITY"] = rg["quality"]
    out["ACCUM_SCORE"] = accumulation_score(df)
    out["DIST_SCORE"] = distribution_score(df)
    ev = all_events(df, lv)
    out = out.join(ev)
    return out
