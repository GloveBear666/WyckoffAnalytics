# -*- coding: utf-8 -*-
"""v2 概念窗口质量抽查: 每个概念打印首窗, 检查语义完整性。"""
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

d = json.load(open("knowledge/factors/concept_windows_v2.json", encoding="utf-8"))
concepts = d["concepts"]
# 重点抽查: 修复前破碎最严重的
for name in ("供求关系", "努力结果", "spring", "恐慌抛售", "因果关系", "震仓"):
    ws = concepts[name]
    print(f"===== {name} ({len(ws)} windows) =====")
    for w in ws[:2]:
        print(f"  p{w['page']}:")
        for s in w["window"]:
            print("   |", s[:75])
    print()

# 完整性审计: 窗口内句子是否都以句末标点结束 (允许 ● 列表项与括号)
import re
bad = 0
total = 0
for name, ws in concepts.items():
    for w in ws:
        for s in w["window"]:
            total += 1
            s = s.strip()
            if s and s[-1] not in "。！？…；)" and not s.startswith("●") and s[-1] not in "●":
                bad += 1
print(f"audit: {total} sentences, {bad} not ending with sentence punctuation")
