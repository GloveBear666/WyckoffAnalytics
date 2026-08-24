# -*- coding: utf-8 -*-
"""检查句子语料质量: 抽样页的段落/句子结构。"""
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = json.load(open("knowledge/raw_text/威科夫操盘法.sentences.json", encoding="utf-8"))
lens = []
for p in c["corpus"]:
    for para in p["paragraphs"]:
        for s in para:
            lens.append(len(s))
import statistics
print(f"total sentences: {len(lens)}")
print(f"len: mean={statistics.mean(lens):.1f} median={statistics.median(lens)} p90={sorted(lens)[int(len(lens)*0.9)]}")
for p in (c["corpus"][17], c["corpus"][24]):
    print(f"--- PAGE {p['page']}: paragraphs={len(p['paragraphs'])}")
    for para in p["paragraphs"][:3]:
        print(f"  para({len(para)} sents):")
        for s in para[:5]:
            print("   |", s[:70])
