# -*- coding: utf-8 -*-
"""抽取指定页范围的原始文本 (辅助检视)。用法: python scripts/dump_pages.py 15 20"""
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

text = open("knowledge/raw_text/威科夫操盘法.txt", encoding="utf-8").read()
pages = text.split("===== [PAGE ")[1:]
lo, hi = int(sys.argv[1]), int(sys.argv[2])
for chunk in pages:
    pno = int(chunk.split("]")[0])
    if lo <= pno <= hi:
        body = chunk.split("] =====", 1)[1]
        body = re.sub(r"\n{2,}", "\n", body)
        print(f"\n--- PAGE {pno} ---")
        print(body[:4200])
