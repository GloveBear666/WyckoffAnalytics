# -*- coding: utf-8 -*-
"""
KNOWLEDGE_INGESTION_LAYER - 知识提取层 (架构模块1)
====================================================
任务: 将威科夫方法源文件(PDF)解析为:
  1. 结构化纯文本 (knowledge/raw_text/)
  2. 章节地图 (knowledge/chapters/)  - 基于字体大小/关键词的标题检测
  3. 摄取清单  (knowledge/ingest_manifest.json)

用法: python ingest/extract_pdfs.py
输出编码: UTF-8
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# 控制台 UTF-8 输出(Windows cp1252 兼容)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "knowledge" / "sources"
RAW_DIR = ROOT / "knowledge" / "raw_text"
CHAP_DIR = ROOT / "knowledge" / "chapters"
MANIFEST_PATH = ROOT / "knowledge" / "ingest_manifest.json"

CHAPTER_KEYWORDS = [
    "章", "节", "篇", "第", "phase", "Phase", "accumulation", "Accumulation",
    "distribution", "Distribution", "spring", "Spring", "upthrust", "Upthrust",
    "vsa", "VSA", "composite", "Composite", "operator", "Operator", "effort",
    "Effort", "cause", "Cause", "effect", "Effect", "trading range", "Trading Range",
    "campaign", "Campaign", "wave", "Wave", "Wyckoff", "价格", "吸筹", "派发",
    "弹簧", "上冲", "努力", "结果", "因果", "资金管理", "庄家", "主力", "量价",
]


@dataclass
class HeadingCandidate:
    page: int
    text: str
    size: float
    bold: bool
    y: float


def extract_pdf(pdf_path: Path) -> tuple[str, list[HeadingCandidate]]:
    """提取全文(带页标记)与标题候选。"""
    doc = fitz.open(pdf_path)
    lines_out: list[str] = []
    headings: list[HeadingCandidate] = []
    size_hist: list[float] = []

    for pno, page in enumerate(doc, start=1):
        lines_out.append(f"\n===== [PAGE {pno}] =====")
        d = page.get_text("dict")

        # 逐行收集 spans，按 y 坐标聚合为行
        line_spans: dict[tuple, list] = {}
        for block in d.get("blocks", []):
            if block.get("type") != 0:  # 非文本块(图片等)
                continue
            for line in block.get("lines", []):
                key = (round(line["bbox"][1], 1), round(line["bbox"][3], 1))
                line_spans.setdefault(key, []).extend(line.get("spans", []))

        for (y0, y1), spans in sorted(line_spans.items()):
            text = "".join(s["text"] for s in spans).strip()
            if not text:
                continue
            max_size = max((s["size"] for s in spans), default=0)
            bold = any("bold" in (s.get("font", "") or "").lower() for s in spans)
            size_hist.append(max_size)
            lines_out.append(text)
            headings.append(HeadingCandidate(pno, text, max_size, bold, y0))

    doc.close()

    # 标题判定: 字号显著大于页内中位数 或 含章节关键词的短行
    if size_hist:
        median_size = float(sorted(size_hist)[len(size_hist) // 2])
    else:
        median_size = 10.0

    def is_heading(h: HeadingCandidate) -> bool:
        kw_hit = any(k in h.text for k in CHAPTER_KEYWORDS)
        short_line = len(h.text) <= 60
        size_big = h.size >= median_size * 1.18 and short_line
        return short_line and (kw_hit or size_big) and not h.text.startswith("=====")

    heading_list = [h for h in headings if is_heading(h)]
    # 合并相邻同页候选(同标题跨span切分)
    merged: list[HeadingCandidate] = []
    for h in heading_list:
        if merged and merged[-1].page == h.page and abs(h.y - merged[-1].y) < 8:
            merged[-1].text = (merged[-1].text + h.text).strip()
            merged[-1].size = max(merged[-1].size, h.size)
        else:
            merged.append(h)
    return "\n".join(lines_out), merged


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CHAP_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"version": "0.1.0", "documents": []}

    for pdf in sorted(SOURCES_DIR.glob("*.pdf")):
        doc_id = pdf.stem
        print(f"[ingest] processing: {pdf.name}", flush=True)
        try:
            text, headings = extract_pdf(pdf)
        except Exception as e:  # noqa: BLE001
            print(f"[ingest] FAILED {pdf.name}: {e}", flush=True)
            manifest["documents"].append({"file": pdf.name, "status": "failed", "error": str(e)})
            continue

        # 归一化空白(保留换行)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        raw_path = RAW_DIR / f"{doc_id}.txt"
        raw_path.write_text(text, encoding="utf-8")

        chap_data = [asdict(h) for h in headings]
        chap_path = CHAP_DIR / f"{doc_id}.chapters.json"
        chap_path.write_text(
            json.dumps({"document": pdf.name, "pages": text.count("[PAGE "), "headings": chap_data},
                       ensure_ascii=False, indent=2), encoding="utf-8")

        manifest["documents"].append({
            "file": pdf.name,
            "doc_id": doc_id,
            "status": "ok",
            "chars": len(text),
            "pages": text.count("[PAGE "),
            "headings_detected": len(chap_data),
            "raw_text": str(raw_path.relative_to(ROOT)),
            "chapters": str(chap_path.relative_to(ROOT)),
        })
        print(f"[ingest] ok: {len(text)} chars, {len(chap_data)} headings", flush=True)

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ingest] manifest -> {MANIFEST_PATH}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
