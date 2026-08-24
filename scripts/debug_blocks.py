# -*- coding: utf-8 -*-
"""调试: 打印指定页的块几何/字体/合并判定。"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fitz

from ingest.extract_sentences import (_collect_blocks, _is_heading, _join_lines,
                                      _reconstruct_paragraphs, HEADING_FONT_RATIO)

import statistics

doc = fitz.open("knowledge/sources/威科夫操盘法.pdf")
for pno in (18, 25):
    blocks = _collect_blocks(doc[pno - 1].get_text("dict"))
    fonts = [b["max_font"] for b in blocks if b["max_font"] > 0]
    med = statistics.median(fonts)
    print(f"=== PAGE {pno}: {len(blocks)} blocks, median_font={med:.1f}")
    for i, b in enumerate(blocks):
        text = _join_lines(b["texts"])
        head = _is_heading(b, med)
        print(f"  [{i}] y0={b['y0']:6.1f} y1={b['y1']:6.1f} x0={b['x0']:6.1f} "
              f"font={b['max_font']:5.1f} head={head} | {text[:38]}")
doc.close()
