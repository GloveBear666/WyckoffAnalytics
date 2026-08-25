# -*- coding: utf-8 -*-
"""
CORE QUIZ LAYER - 试卷盲测系统 (Cyborg Trading System 第一阶段)
===============================================================
闭环流程: 随机截取(盲盒生成) -> 人类答题(模块1/2/3) -> 自动批改(未来N根) -> MFE/MAE标注 -> 错题统计 -> 标注集导出

对齐 Cyborg_Trading_System_Summary.md:
  * 盲盒: 固定 window 根K线 (默认 120x4H), 隐藏未来走势
  * 模块1 (强弱度分位数): A 绝对强势 / B 相对强势 / C 混沌状态 / D 绝对弱势
  * 模块2 (努力与结果的验证, 最右端最新3根K线):
        A 无量空跌 (No Supply) / B 巨量不跌 (Buying Absorb)
        C 无量反弹 (No Demand) / D 放量滞涨 (Distribution)
  * 模块3 (盈亏比预判): A 是 (SL->TP 盈亏比 >= 3:1) / B 否
  * 批改 (自动对答案, 未来 future 根K线, 止损优先):
        ❌ STOP    0分   未来K线最低价跌破预设止损价 (过程破位即被风控出局)
        ✅ TARGET 100分  触及止损前最高价达到 2R 目标 (准确抓住启动点)
        ⚠️ TIMEOUT 50分   未来走完未破止损也未达 2R (误判震荡中继为启动点)
  * 标注 (黄金数据集): [K线矩阵(window,5)] + [人类标注] + [未来真实结果] -> JSONL
"""
from __future__ import annotations

import json
import random
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
QUIZ_DIR = ROOT / "research" / "quiz"
LABEL_DIR = QUIZ_DIR / "labels"

# --------------------------------------------------------------------------
# 理论框架 (与 Summary 文档逐字对齐)
# --------------------------------------------------------------------------
M1 = {
    "A": {"name": "绝对强势", "desc": "吸筹尾声/启动前夜: 供需失衡, 供应消耗殆尽 (高胜率做多点)", "direction": 1},
    "B": {"name": "相对强势", "desc": "趋势中继回踩: Markup 阶段的正常缩量回调 (中胜率加仓点)", "direction": 1},
    "C": {"name": "混沌状态", "desc": "震荡市/无主力: 量价随机, 无主力控盘痕迹 (观望)", "direction": 0},
    "D": {"name": "绝对弱势", "desc": "派发阶段/出货完毕: 大量大阴线, 努力与结果严重背离 (高胜率做空点)", "direction": -1},
}
M2 = {
    "A": {"name": "无量空跌", "desc": "No Supply Test: 价格创新低或回踩, 成交量极度萎缩 (无人抛售)"},
    "B": {"name": "巨量不跌", "desc": "Buying Absorb: 成交量巨大且收盘在K线上中部 (主力暗中接盘)"},
    "C": {"name": "无量反弹", "desc": "No Demand: 价格上涨, 成交量极度萎缩 (散户跟风, 假突破预警)"},
    "D": {"name": "放量滞涨", "desc": "Distribution: 成交量巨大, 实体小且留长上影线 (高位抛压)"},
}
M3 = {
    "A": {"name": "是", "desc": "技术止损位(SL)到第一压力位(TP)盈亏比 >= 3:1 (完美点位)"},
    "B": {"name": "否", "desc": "方向看对但空间狭窄, 不值得冒险"},
}
OUTCOME = {
    "STOP":    {"label": "绝对错误 (Stopped Out)",          "score": 0,   "icon": "❌",
                "logic": "无论后续涨多少, 过程破位即被风控出局, 进场点判断错误。"},
    "TARGET":  {"label": "完美正确 (Target Achieved)",      "score": 100, "icon": "✅",
                "logic": "准确抓住威科夫启动点, 并给风控留出足够安全空间。"},
    "TIMEOUT": {"label": "尴尬平局 (Time Out / Flat)",      "score": 50,  "icon": "⚠️",
                "logic": "误判震荡中继为启动点, 未亏钱但浪费资金时间成本。"},
    "NO_TRADE": {"label": "观望 (未交易)",                   "score": None, "icon": "🚫",
                "logic": "不满足入场条件, 不做交易 (记录潜在结果用于检验判断)。"},
}

DEFAULT_WINDOW = 120   # 盲盒长度 (根K线, 文档默认 120 x 4H)
DEFAULT_FUTURE = 60    # 未来验证长度 (根K线, 文档默认 60)
TARGET_R = 2.0         # 完美正确阈值: 触及止损前达到 2R
LOOKBACK_STOP = 20     # 建议止损回看: 最近 N 根的高低点
ATR_BUFFER = 0.5       # 建议止损缓冲: 0.5 倍 ATR


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> float:
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    return float(np.mean(tr[-n:])) if len(tr) else 0.0


def _bars(df: pd.DataFrame) -> list:
    out = []
    for ts, r in df.iterrows():
        out.append([ts.isoformat(), round(float(r["open"]), 8), round(float(r["high"]), 8),
                    round(float(r["low"]), 8), round(float(r["close"]), 8), round(float(r["volume"]), 4)])
    return out


def _simulate(bars: list, entry: float, direction: int, stop: float, target_r: float = TARGET_R) -> dict:
    """模拟未来走势: 止损优先 (与回测引擎一致)。

    bars: [(ts,o,h,l,c,v), ...]
    返回: 结局代码/分数/MFE(R)/MAE(R)/MAE占止损距离%/出场价/出场时间/持有根数/目标价。
    """
    R = abs(entry - stop)
    if R <= 0:
        raise ValueError("止损价必须与进场价拉开距离")
    tp2 = entry + direction * R * 2.0
    tp3 = entry + direction * R * 3.0
    mfe, mae = 0.0, 0.0
    code = "TIMEOUT"
    exit_price = float(bars[-1][4])
    exit_dt = bars[-1][0]
    bars_held = len(bars)
    for i, (ts, o, h, l, _c, _v) in enumerate(bars, 1):
        if direction == 1:
            # 先记录本根极值 (MFE/MAE 含出场当根, 标准定义)
            mfe = max(mfe, (h - entry) / R)
            mae = max(mae, (entry - l) / R)
            if l <= stop:
                code = "STOP"; exit_price = min(float(stop), float(o)); exit_dt = ts; bars_held = i; break
            if h >= tp2:
                code = "TARGET"; exit_price = float(tp2); exit_dt = ts; bars_held = i; break
        else:
            # 空头: 有利=下跌(用最低价), 不利=上涨(用最高价)
            mfe = max(mfe, (entry - l) / R)
            mae = max(mae, (h - entry) / R)
            if h >= stop:
                code = "STOP"; exit_price = max(float(stop), float(o)); exit_dt = ts; bars_held = i; break
            if l <= tp2:
                code = "TARGET"; exit_price = float(tp2); exit_dt = ts; bars_held = i; break
    return {
        "code": code, "score": OUTCOME[code]["score"],
        "r": round(R, 8), "target_2r": round(tp2, 8), "target_3r": round(tp3, 8),
        "mfe_r": round(mfe, 3), "mae_r": round(mae, 3),
        "mae_pct": round(min(100.0, mae * 100.0), 1),
        "exit_price": round(exit_price, 8), "exit_dt": exit_dt, "bars_held": bars_held,
    }


# --------------------------------------------------------------------------
# 题库仓库
# --------------------------------------------------------------------------
class QuizStore:
    """盲盒题目生成 / 批改 / 记录持久化 / 统计分析 / 标注集导出。"""

    def __init__(self, base: Path = QUIZ_DIR):
        self.base = Path(base)
        (self.base / "labels").mkdir(parents=True, exist_ok=True)
        self.records_file = self.base / "records.jsonl"
        self.label_dir = self.base / "labels"
        self.items: dict[str, dict] = {}          # item_id -> item (含未来数据, 仅服务端)
        self._used: dict[tuple, set] = {}          # (profile,symbol,tf) -> 已用 start 下标

    # ---------------- 盲盒生成 ----------------
    def new_item(self, df: pd.DataFrame, window: int = DEFAULT_WINDOW,
                 future: int = DEFAULT_FUTURE, key: tuple | None = None) -> dict:
        n = len(df)
        max_start = n - window - future
        if max_start < 1:
            raise ValueError(f"数据不足: 至少需要 {window + future + 1} 根K线, 当前仅 {n} 根")
        used = self._used.setdefault(key, set())
        rng = random.Random(time.time_ns())
        candidates = [i for i in range(max_start + 1) if i not in used]
        if not candidates:
            used.clear()
            candidates = list(range(max_start + 1))
        start = rng.choice(candidates)
        used.add(start)

        vis = df.iloc[start:start + window]
        fut = df.iloc[start + window:start + window + future]
        entry_price = float(vis["close"].iloc[-1])
        h = vis["high"].to_numpy(float)
        l = vis["low"].to_numpy(float)
        c = vis["close"].to_numpy(float)
        atr = _atr(h, l, c)
        buffer = ATR_BUFFER * atr
        ds_long = float(l[-LOOKBACK_STOP:].min() - buffer)
        ds_short = float(h[-LOOKBACK_STOP:].max() + buffer)

        item = {
            "item_id": uuid.uuid4().hex[:12],
            "profile": key[0] if key else None,
            "symbol": key[1] if key else None,
            "tf": key[2] if key else None,
            "window": int(window), "future": int(future),
            "start_dt": vis.index[0].isoformat(),
            "visible_end_dt": vis.index[-1].isoformat(),
            "entry_price": entry_price,
            "atr": round(atr, 8),
            "default_stop_long": round(ds_long, 8),
            "default_stop_short": round(ds_short, 8),
            "visible": _bars(vis),
            "future_bars": _bars(fut),   # 仅存服务端, API 不下发
            "answered": False,
        }
        self.items[item["item_id"]] = item
        out = {k: v for k, v in item.items() if k != "future_bars"}   # 盲盒载荷: 隐藏未来走势!
        return out

    # ---------------- 批改 ----------------
    def grade(self, item_id: str, m1: str, m2: str, m3: str, stop: float | None) -> dict:
        item = self.items.get(item_id)
        if item is None:
            raise ValueError("题目不存在或已过期, 请重新抽题")
        if item.get("answered"):
            raise ValueError("该题已批改过, 请抽取新题目")
        if m1 not in M1 or m2 not in M2 or m3 not in M3:
            raise ValueError("答案格式错误 (模块1/2/3 必须为 A/B/C/D)")
        direction = M1[m1]["direction"]
        entry = item["entry_price"]

        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "item_id": item_id,
            "profile": item["profile"], "symbol": item["symbol"], "tf": item["tf"],
            "window": item["window"], "future": item["future"],
            "start_dt": item["start_dt"], "entry_dt": item["visible_end_dt"],
            "entry": entry,
            "m1": m1, "m2": m2, "m3": m3, "direction": direction,
            "features": [[b[1], b[2], b[3], b[4], b[5]] for b in item["visible"]],
        }

        if direction == 0 or m3 == "B":
            # 观望 (混沌) 或 空间不足: 不交易, 但记录"如果入场"的潜在结果, 检验克制是否正确
            reason = "混沌状态观望" if direction == 0 else "盈亏比不足(空间狭窄) 放弃"
            sl = _simulate(item["future_bars"], entry, 1, item["default_stop_long"])
            ss = _simulate(item["future_bars"], entry, -1, item["default_stop_short"])
            abstain_ok = sl["mfe_r"] < TARGET_R and ss["mfe_r"] < TARGET_R
            rec.update({
                "outcome": "NO_TRADE", "score": None, "reason": reason,
                "abstain_ok": bool(abstain_ok),
                "would_be": {
                    "long": {"stop": item["default_stop_long"], "code": sl["code"],
                             "mfe_r": sl["mfe_r"], "mae_r": sl["mae_r"]},
                    "short": {"stop": item["default_stop_short"], "code": ss["code"],
                              "mfe_r": ss["mfe_r"], "mae_r": ss["mae_r"]},
                },
            })
            payload = {
                "outcome": "NO_TRADE", "label": OUTCOME["NO_TRADE"]["label"],
                "icon": OUTCOME["NO_TRADE"]["icon"], "score": None,
                "reason": reason, "abstain_ok": abstain_ok,
                "would_be": rec["would_be"],
                "future_bars": item["future_bars"],
            }
        else:
            try:
                stop = float(stop)
            except (TypeError, ValueError):
                raise ValueError("请输入有效止损价") from None
            if direction == 1 and not (stop < entry):
                raise ValueError("做多止损价必须低于进场价")
            if direction == -1 and not (stop > entry):
                raise ValueError("做空止损价必须高于进场价")
            sim = _simulate(item["future_bars"], entry, direction, stop)
            rec.update({
                "stop": round(stop, 8), "outcome": sim["code"], "score": sim["score"],
                "exit_dt": sim["exit_dt"], "exit_price": sim["exit_price"],
                "bars_held": sim["bars_held"], "mfe_r": sim["mfe_r"],
                "mae_r": sim["mae_r"], "mae_pct": sim["mae_pct"],
            })
            payload = {
                "outcome": sim["code"], "label": OUTCOME[sim["code"]]["label"],
                "icon": OUTCOME[sim["code"]]["icon"], "score": sim["score"],
                "logic": OUTCOME[sim["code"]]["logic"],
                "entry": entry, "stop": stop, "direction": direction,
                "r": sim["r"], "target_2r": sim["target_2r"], "target_3r": sim["target_3r"],
                "mfe_r": sim["mfe_r"], "mae_r": sim["mae_r"], "mae_pct": sim["mae_pct"],
                "exit_price": sim["exit_price"], "exit_dt": sim["exit_dt"],
                "bars_held": sim["bars_held"],
                "future_bars": item["future_bars"],
            }

        item["answered"] = True
        with self.records_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return payload

    # ---------------- 记录 / 统计 ----------------
    def load_records(self) -> list[dict]:
        if not self.records_file.exists():
            return []
        out = []
        with self.records_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    @staticmethod
    def _group(records: list[dict], field: str, key: str) -> dict:
        rows = [r for r in records if r.get(field) == key]
        n = len(rows)
        if n == 0:
            return {"n": 0, "target": 0, "stop": 0, "timeout": 0,
                    "win_rate": None, "avg_score": None, "pie_rate": None}
        target = sum(1 for r in rows if r["outcome"] == "TARGET")
        stop = sum(1 for r in rows if r["outcome"] == "STOP")
        return {
            "n": n, "target": target, "stop": stop, "timeout": n - target - stop,
            "win_rate": round(target / n, 4),
            "avg_score": round(sum(r["score"] for r in rows) / n, 1),
            "pie_rate": round(stop / n, 4),   # 画饼率: 看对方向却被止损 (认知漏洞检测)
        }

    def stats(self) -> dict:
        records = self.load_records()
        graded = [r for r in records if r.get("outcome") != "NO_TRADE"]
        n = len(graded)

        def rate(f: str) -> float | None:
            return round(sum(1 for r in graded if r["outcome"] == f) / n, 4) if n else None

        base = {
            "total": len(records), "graded": n, "no_trade": len(records) - n,
            "avg_score": round(sum(r["score"] for r in graded) / n, 1) if n else None,
            "perfect_rate": rate("TARGET"), "stop_rate": rate("STOP"), "timeout_rate": rate("TIMEOUT"),
            "avg_mfe_r": round(sum(r["mfe_r"] for r in graded) / n, 3) if n else None,
            "avg_mae_r": round(sum(r["mae_r"] for r in graded) / n, 3) if n else None,
            "avg_mae_pct": round(sum(r["mae_pct"] for r in graded) / n, 1) if n else None,
        }
        by_m1 = {k: self._group(graded, "m1", k) for k in M1}
        by_m2 = {k: self._group(graded, "m2", k) for k in M2}
        abst = [r for r in records if r.get("m3") == "B"]
        missed = 0
        for r in abst:
            d = M1[r["m1"]]["direction"]
            if d != 0:
                wb = r["would_be"]["long" if d == 1 else "short"]
                if wb["mfe_r"] >= TARGET_R:
                    missed += 1
        abstain = [r for r in records if r.get("outcome") == "NO_TRADE"]
        wrong_top = [r for r in records if r.get("outcome") == "STOP"][-10:][::-1]
        return {
            "stats": base,
            "by_m1": by_m1, "by_m2": by_m2,
            "m3_B": {"n": len(abst), "missed": missed, "correct": len(abst) - missed},
            "abstain": {"n": len(abstain),
                        "correct": sum(1 for r in abstain if r.get("abstain_ok"))},
            "recent": records[-20:][::-1],
            "wrong_top": wrong_top,
        }

    # ---------------- 标注集导出 (AI 训练燃料) ----------------
    def export(self, symbol: str | None = None, tf: str | None = None) -> dict:
        records = self.load_records()
        if symbol:
            records = [r for r in records if r.get("symbol") == symbol]
        if tf:
            records = [r for r in records if r.get("tf") == tf]
        if not records:
            raise ValueError("没有可导出的答题记录 (请先完成答题)")
        fname = f"quiz_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        path = self.label_dir / fname
        with path.open("w", encoding="utf-8") as f:
            for r in records:
                line = {
                    "item_id": r["item_id"], "symbol": r["symbol"], "tf": r["tf"],
                    "window": r["window"], "future": r["future"],
                    "start_dt": r["start_dt"], "entry_dt": r["entry_dt"],
                    "features": r["features"],   # K线矩阵 (window,5): [o,h,l,c,v]
                    "human": {"m1": r["m1"], "m2": r["m2"], "m3": r["m3"],
                              "direction": r["direction"], "entry": r["entry"],
                              "stop": r.get("stop")},
                    "outcome": {"code": r["outcome"], "score": r.get("score"),
                                "mfe_r": r.get("mfe_r"), "mae_r": r.get("mae_r"),
                                "exit_dt": r.get("exit_dt"), "exit_price": r.get("exit_price"),
                                "bars_held": r.get("bars_held")},
                }
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return {"file": fname, "count": len(records), "path": str(path)}
