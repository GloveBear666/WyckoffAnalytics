# -*- coding: utf-8 -*-
"""
答题评测系统核心层冒烟测试:
  1) 加载 BTC 4H 数据
  2) 连续抽 5 个盲盒 (窗口120/未来60)
  3) 分别以 做多/做空/观望/盈亏比不足 交卷
  4) 校验统计与标注导出
用法: python -X utf8 scripts/quiz_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.data import load_data
from core.quiz import QUIZ_DIR, M1, M2, M3, QuizStore

TMP = QUIZ_DIR / "_smoke"
TMP.mkdir(parents=True, exist_ok=True)
store = QuizStore(base=TMP)

df = load_data("BTC/USDT", "crypto", "4h")
print(f"[1] 数据: {len(df)} bars  {df.index[0]} -> {df.index[-1]}")

key = ("crypto", "BTC/USDT", "4h")
payloads = []
for i in range(5):
    item = store.new_item(df, window=120, future=60, key=key)
    full = store.items[item["item_id"]]           # 服务端完整题目 (含未来, 不下发)
    assert len(item["visible"]) == 120 and len(full["future_bars"]) == 60
    assert item["future"] == 60
    assert "future_bars" not in item, "盲盒载荷不得泄露未来数据"
    assert item["entry_price"] > 0
    print(f"[2] 盲盒{i+1}: {item['item_id']} 起点 {item['start_dt'][:16]}  "
          f"进场 {item['entry_price']:.2f} 建议止损 多{item['default_stop_long']:.2f}/空{item['default_stop_short']:.2f}")

    m1 = ["A", "D", "C", "B", "A"][i]
    m2 = ["B", "D", "A", "A", "C"][i]
    m3 = ["A", "A", "A", "B", "A"][i]
    stop = item["default_stop_long"] if M1[m1]["direction"] == 1 else item["default_stop_short"]
    p = store.grade(item["item_id"], m1, m2, m3, stop)
    payloads.append(p)
    print(f"    -> {p['outcome']:8s} 分数={p.get('score')} MFE={p.get('mfe_r')}R MAE={p.get('mae_r')}R "
          f"持有={p.get('bars_held')}根 出场={p.get('exit_price')}")

# 校验批改数学: 做多 STOP 必须发生在 TARGET 之前 (止损优先)
for p in payloads:
    if p["outcome"] == "TARGET":
        assert p["mfe_r"] >= 2.0 - 1e-6, f"TARGET 但 MFE<2R: {p['mfe_r']}"
    if p["outcome"] == "STOP":
        assert p["mae_r"] >= 1.0 - 1e-6, f"STOP 但 MAE<1R: {p['mae_r']}"

s = store.stats()
print(f"[3] 统计: 答卷={s['stats']['total']} 交易={s['stats']['graded']} 观望={s['stats']['no_trade']} "
      f"平均分={s['stats']['avg_score']} 完美率={s['stats']['perfect_rate']} 止损率={s['stats']['stop_rate']}")
print(f"    by_m1: " + ", ".join(f"{k}:{v['n']}" for k, v in s["by_m1"].items()))
print(f"    m3_B(放弃) 错过={s['m3_B']['missed']}/{s['m3_B']['n']}  观望正确={s['abstain']['correct']}/{s['abstain']['n']}")

info = store.export()
print(f"[4] 标注导出: {info['count']} 条 -> {info['path']}")
with open(info["path"], "r", encoding="utf-8") as f:
    line = f.readline()
import json
rec = json.loads(line)
assert len(rec["features"]) == 120 and len(rec["features"][0]) == 5
assert {"m1", "m2", "m3", "direction", "entry"} <= set(rec["human"])
assert rec["outcome"]["code"] in ("TARGET", "STOP", "TIMEOUT", "NO_TRADE")
print(f"    首条: features={len(rec['features'])}x{len(rec['features'][0])} human={rec['human']['m1']} "
      f"outcome={rec['outcome']['code']}  ✓ 黄金数据集格式正确")

print("[PASS] 答题系统核心层冒烟测试全部通过")
