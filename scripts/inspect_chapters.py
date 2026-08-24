# -*- coding: utf-8 -*-
"""检视章节地图质量: 打印章/节级标题候选。"""
import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

d = json.load(open("knowledge/chapters/威科夫操盘法.chapters.json", encoding="utf-8"))
hs = d["headings"]
print(f"total headings: {len(hs)}")
chap_pat = re.compile(r"第[一二三四五六七八九十百0-9]+[章节篇]")
seen = set()
for h in hs:
    t = h["text"].strip()
    if len(t) <= 32 and chap_pat.search(t) and t not in seen:
        seen.add(t)
        print(f"  p{h['page']:>3} [{h['size']:5.1f}pt] {t}")
