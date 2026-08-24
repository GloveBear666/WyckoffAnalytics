# -*- coding: utf-8 -*-
"""
EXECUTION_ENGINE - 温度控制信号层 (架构模块3)
================================================
将因子/事件矩阵 + 温度参数 T∈[0.1,1.0] 合成交易信号。

温度语义 (config/temperature.json):
  T=0.1 低容忍: 多因子共振(≥3), 严格止损(0.5 ATR), 高盈亏比(3.0), 小头寸
  T=1.0 高容忍: 单因子触发(≥1), 宽幅止损(2.0 ATR), 盈亏比(1.5), 大头寸

信号在 bar t 收盘判定, 引擎在 t+1 开盘执行 (无前视偏差)。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from core.indicators import build_feature_frame

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "temperature.json"


# --------------------------------------------------------------------------
# 温度插值
# --------------------------------------------------------------------------
def _lerp(lo_val, hi_val, t: float):
    """线性插值, t∈[0,1] 映射 T:0.1→0, T:1.0→1。"""
    return lo_val + (hi_val - lo_val) * t


def _interp_value(spec, t: float):
    """对 temperature.json 中的单参数字典 {T0.1:.., T1.0:..} 插值。"""
    lo, hi = spec["T0.1"], spec["T1.0"]
    if isinstance(lo, bool) and isinstance(hi, bool):
        return hi if t >= 0.5 else lo
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return float(_lerp(lo, hi, t))
    if isinstance(lo, list) and isinstance(hi, list):
        return [float(_lerp(a, b, t)) for a, b in zip(lo, hi)]
    raise TypeError(f"unsupported param spec: {spec}")


def temperature_params(T: float, config_path: Path = CONFIG_PATH) -> dict:
    """T∈[0.1,1.0] -> 完整参数字典。"""
    assert 0.1 <= T <= 1.0, "T must be in [0.1, 1.0]"
    t = (T - 0.1) / 0.9
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    params: dict = {"T": T}
    for group, group_map in cfg["parameter_maps"].items():
        for name, spec in group_map.items():
            params[f"{group}.{name}"] = _interp_value(spec, t)
    return params


# --------------------------------------------------------------------------
# 因子共振
# --------------------------------------------------------------------------
def _long_factor_count(f: pd.DataFrame, p: dict) -> pd.Series:
    """多头方向活跃因子计数 (全向量化)。"""
    n = f["EVT_SPRING"].astype(int)
    n = n + f["EVT_ST"].astype(int)
    n = n + f["EVT_SHAKEOUT"].astype(int)
    n = n + f["EVT_SOS"].astype(int)
    n = n + f["EVT_JOC"].astype(int)
    n = n + f["EVT_STOP_ACTION"].astype(int)
    n = n + (f["ACCUM_SCORE"] > 0.55).astype(int)
    n = n + (f["SUPPLY_EXHAUST"] < 0.70).astype(int)
    n = n + (f["UPVOL_RATIO"] > 0.50).astype(int)
    n = n + (f["LOWER_WICK"] > 0.40).astype(int)
    n = n + ((f["REGIME_QUALITY"] >= p["filters.regime_quality_min"]) & (f["REGIME"] >= 0)).astype(int)
    n = n + (f["DEMAND_GROWTH"] > 0.0).astype(int)
    return n.fillna(0)


def _short_factor_count(f: pd.DataFrame, p: dict) -> pd.Series:
    """空头方向活跃因子计数 (全向量化)。"""
    n = f["EVT_UT"].astype(int)
    n = n + f["EVT_SOW"].astype(int)
    n = n + f["EVT_BC"].astype(int)
    n = n + (f["DIST_SCORE"] > 0.55).astype(int)
    n = n + (f["UPPER_WICK"] > 0.40).astype(int)
    n = n + (f["UPVOL_RATIO"] < 0.45).astype(int)
    n = n + ((f["REGIME_QUALITY"] >= p["filters.regime_quality_min"]) & (f["REGIME"] <= 0)).astype(int)
    return n.fillna(0)


# --------------------------------------------------------------------------
# 信号生成
# --------------------------------------------------------------------------
def _cooldown_mask(mask: pd.Series, index: pd.Index, cooldown: int) -> pd.Series:
    """同方向入场冷却: 每个信号簇只保留首根 (cooldown 根K线内不重复)。"""
    if cooldown <= 0:
        return mask
    keep: list = []
    last = None
    for i, t in enumerate(index):
        if mask.iloc[i] and (last is None or i - last >= cooldown):
            keep.append(t)
            last = i
    out = pd.Series(False, index=index)
    out.loc[keep] = True
    return out


def _as_naive_utc(idx: pd.Index) -> pd.DatetimeIndex:
    """归一化为无时区UTC时间戳 (消除 naive/aware dtype 不匹配)。"""
    di = pd.DatetimeIndex(idx)
    if di.tz is not None:
        di = di.tz_convert("UTC").tz_localize(None)
    return di


def _align_htf(htf_feat: pd.DataFrame, base_index: pd.Index) -> pd.DataFrame:
    """将 HTF 特征按时间戳回填对齐到基础时间框架 (merge_asof backward)。
    每个基础bar取"最近一个已完成"的HTF bar (无前视: HTF收盘<=基础bar时间)。"""
    base = pd.DataFrame({"ts": _as_naive_utc(base_index)})
    h = htf_feat.copy()
    h["htf_ts"] = _as_naive_utc(h.index)
    m = pd.merge_asof(base, h, left_on="ts", right_on="htf_ts", direction="backward")
    m.index = base_index
    return m.drop(columns=["ts", "htf_ts"])


def htf_context(htf: pd.DataFrame, base_index: pd.Index, window: int = 60) -> pd.DataFrame:
    """计算 HTF 环境上下文: 趋势/吸筹/派发评分 + 近期SC/ST事件 (多周期确认)。"""
    f = build_feature_frame(htf, window=window)
    out = pd.DataFrame(index=htf.index)
    out["HTF_REGIME"] = f["REGIME"]
    out["HTF_ACCUM"] = f["ACCUM_SCORE"]
    out["HTF_DIST"] = f["DIST_SCORE"]
    out["HTF_SC_RECENT"] = f["EVT_SC"].rolling(8, min_periods=3).max().fillna(0) > 0
    out["HTF_SPRING_RECENT"] = f["EVT_SPRING"].rolling(8, min_periods=3).max().fillna(0) > 0
    out["HTF_QUALITY"] = f["REGIME_QUALITY"]
    return _align_htf(out, base_index)


def generate_signals(df: pd.DataFrame, T: float = 0.5,
                     feature_window: int = 60, entry_cooldown: int = 5,
                     htf: pd.DataFrame | None = None) -> pd.DataFrame:
    """生成信号帧 (收盘决策, 无前视):
    列: SIGNAL(+1/-1/0), ENTRY_PRICE, STOP_PRICE, TARGET_PRICE, SETUP, CONFIDENCE, FACTOR_N
    htf: 可选高层级时间框架 DataFrame (多周期确认门控, 迭代v0.2)。
    """
    p = temperature_params(T)
    f = build_feature_frame(df, window=feature_window)

    vol_band_lo, vol_band_hi = p["filters.volatility_band"]
    atr_pct = f["ATR"] / f["close"]
    vol_ok = (atr_pct >= vol_band_lo / 100) & (atr_pct <= vol_band_hi / 100)

    out = pd.DataFrame(index=df.index)
    out["SIGNAL"] = 0
    out["ENTRY_PRICE"] = np.nan
    out["STOP_PRICE"] = np.nan
    out["TARGET_PRICE"] = np.nan
    out["SETUP"] = ""
    out["CONFIDENCE"] = 0.0
    out["FACTOR_N"] = 0

    min_res = int(p["signal.factor_resonance_min"])
    vol_min = p["filters.volume_zscore_min"]

    # ---- 多头设置 (吸筹侧) ----
    long_mask = pd.Series(False, index=df.index)
    long_setup = pd.Series("", index=df.index)

    # 1. Spring 进场
    m = f["EVT_SPRING"] & (f["VOL_Z"] >= vol_min) & vol_ok
    long_mask |= m.fillna(False)
    long_setup = long_setup.mask(m, "SPRING")

    # 2. 二次测试进场 (熊市终止确认链: SC->AR->ST, 书p66/p79: ST须在SC后出现)
    sc_recent = f["EVT_SC"].rolling(60, min_periods=20).max().fillna(0) > 0
    m = f["EVT_ST"] & sc_recent & (f["REGIME"] <= 0) & vol_ok
    long_mask |= m.fillna(False)
    long_setup = long_setup.mask(m, "SECONDARY_TEST")

    # 3. 终极震仓进场
    m = f["EVT_SHAKEOUT"] & (f["ACCUM_SCORE"] > 0.5) & vol_ok
    long_mask |= m.fillna(False)
    long_setup = long_setup.mask(m, "SHAKEOUT")

    # 4. SOS/JOC 突破进场 (区间右边界)
    m = (f["EVT_SOS"] | f["EVT_JOC"]) & (f["REGIME"] >= 0) & vol_ok
    long_mask |= m.fillna(False)
    long_setup = long_setup.mask(m, "SOS_JOC")

    # 5. 停止行为 + 死角 (提前进场)
    m = f["EVT_STOP_ACTION"] & (f["ACCUM_SCORE"] > 0.5) & vol_ok
    long_mask |= m.fillna(False)
    long_setup = long_setup.mask(m, "STOP_ACTION")

    # 因子共振门槛 (温度核心逻辑, 全向量化)
    fn = _long_factor_count(f, p)
    long_mask &= fn >= min_res

    # ---- 空头设置 (派发侧) ----
    short_mask = pd.Series(False, index=df.index)
    short_setup = pd.Series("", index=df.index)

    m = f["EVT_UT"] & (f["VOL_Z"] >= vol_min) & vol_ok
    short_mask |= m.fillna(False)
    short_setup = short_setup.mask(m, "UPTHRUST")

    m = f["EVT_SOW"] & vol_ok
    short_mask |= m.fillna(False)
    short_setup = short_setup.mask(m, "SOW")

    m = f["EVT_BC"] & (f["DIST_SCORE"] > 0.5) & vol_ok
    short_mask |= m.fillna(False)
    short_setup = short_setup.mask(m, "BUYING_CLIMAX")

    fn_s = _short_factor_count(f, p)
    short_mask &= fn_s >= min_res

    # ---- HTF 多周期确认门控 (v0.2 迭代) ----
    if htf is not None:
        ctx = htf_context(htf, df.index, window=feature_window)
        long_ok_htf = (ctx["HTF_REGIME"] >= 0) | ctx["HTF_SC_RECENT"] | ctx["HTF_SPRING_RECENT"] \
            | (ctx["HTF_ACCUM"] > 0.5)
        short_ok_htf = (ctx["HTF_REGIME"] <= 0) | (ctx["HTF_DIST"] > 0.5)
        long_mask &= long_ok_htf.fillna(False)
        short_mask &= short_ok_htf.fillna(False)
        # HTF 对齐作为共振因子 +1
        fn = fn + long_ok_htf.fillna(False).astype(int)
        fn_s = fn_s + short_ok_htf.fillna(False).astype(int)

    # 同方向入场冷却 (避免连续信号重复开仓)
    long_mask = _cooldown_mask(long_mask.fillna(False), df.index, entry_cooldown)
    short_mask = _cooldown_mask(short_mask.fillna(False), df.index, entry_cooldown)

    # ---- 落盘 ----
    entry = f["close"]
    a = f["ATR"]

    out.loc[long_mask, "SIGNAL"] = 1
    out.loc[long_mask, "ENTRY_PRICE"] = entry[long_mask]
    out.loc[long_mask, "STOP_PRICE"] = entry[long_mask] - p["risk.stop_atr_mult"] * a[long_mask]
    out.loc[long_mask, "TARGET_PRICE"] = entry[long_mask] + p["risk.take_profit_rr"] * (
        entry[long_mask] - (entry[long_mask] - p["risk.stop_atr_mult"] * a[long_mask]))
    out.loc[long_mask, "SETUP"] = long_setup[long_mask]
    out.loc[long_mask, "CONFIDENCE"] = (fn[long_mask] / 12.0).clip(0, 1)
    out.loc[long_mask, "FACTOR_N"] = fn[long_mask]

    out.loc[short_mask, "SIGNAL"] = -1
    out.loc[short_mask, "ENTRY_PRICE"] = entry[short_mask]
    out.loc[short_mask, "STOP_PRICE"] = entry[short_mask] + p["risk.stop_atr_mult"] * a[short_mask]
    out.loc[short_mask, "TARGET_PRICE"] = entry[short_mask] - p["risk.take_profit_rr"] * (
        p["risk.stop_atr_mult"] * a[short_mask])
    out.loc[short_mask, "SETUP"] = short_setup[short_mask]
    out.loc[short_mask, "CONFIDENCE"] = (fn_s[short_mask] / 8.0).clip(0, 1)
    out.loc[short_mask, "FACTOR_N"] = fn_s[short_mask]

    out["ATR"] = a
    out["REGIME"] = f["REGIME"]
    out["ACCUM_SCORE"] = f["ACCUM_SCORE"]
    out["DIST_SCORE"] = f["DIST_SCORE"]
    return out


def summarize_signals(sig: pd.DataFrame) -> dict:
    """信号统计摘要。"""
    n = int((sig["SIGNAL"] != 0).sum())
    longs = int((sig["SIGNAL"] == 1).sum())
    shorts = int((sig["SIGNAL"] == -1).sum())
    top = (sig.loc[sig["SIGNAL"] != 0, "SETUP"].value_counts().head(6).to_dict()
           if n else {})
    return {"signals": n, "long": longs, "short": shorts, "by_setup": top}
