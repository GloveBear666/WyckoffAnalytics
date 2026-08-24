# -*- coding: utf-8 -*-
"""
KNOWLEDGE_INGESTION_LAYER - 句子级语料构建器 (v0.3)
====================================================
修复 v0.1 行级切割导致的语义破碎 (该PDF文本块≈单行):
  1. 块级阅读顺序排序 (y→x)
  2. 基于字体大小识别标题块 (>=1.35×中位字号 且短行), 标题行跨块合并
  3. 跨块段落重建: 上一块未以句末标点结束 + 纵向间隙小 + 左对齐 -> 合并
  4. 标点分句 -> 完整句子语料 JSON
用法: python ingest/extract_sentences.py
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "knowledge" / "sources"
CORPUS_DIR = ROOT / "knowledge" / "raw_text"

SENT_END = "。！？!?…"
SENT_SPLIT = re.compile(fr"(?<=[{SENT_END}])")
MIN_SENT_LEN = 6
HEADING_FONT_RATIO = 1.35
MAX_HEADING_CHARS = 45


def _collect_blocks(d: dict) -> list[dict]:
    """页内文本块: 阅读顺序排序, 附加字体信息。"""
    blocks = []
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = []
        max_font = 0.0
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(s["text"] for s in spans).strip()
            if not text:
                continue
            max_font = max(max_font, max((s["size"] for s in spans), default=0))
            bbox = line["bbox"]
            lines.append((bbox[1], bbox[0], text))
        if not lines:
            continue
        lines.sort(key=lambda t: (round(t[0], 1), t[1]))
        bbox = block["bbox"]
        blocks.append({"y0": bbox[1], "y1": bbox[3], "x0": bbox[0],
                       "max_font": max_font,
                       "texts": [t[2] for t in lines]})
    blocks.sort(key=lambda b: (round(b["y0"], 1), b["x0"]))
    return blocks


def _join_lines(lines: list[str]) -> str:
    """拼接块内文本行; 还原行尾截断 (中文直连, 拉丁补空格)。"""
    out = ""
    for ln in lines:
        if not ln:
            continue
        if out:
            if out[-1] in SENT_END or ln[0] in "（(【[“‘" or out[-1] in "（(【[“‘":
                out += ln
            elif out[-1].isascii() and ln[0].isascii():
                out += " " + ln
            else:
                out += ln
        else:
            out = ln
    return out


def _is_heading(block: dict, median_font: float) -> bool:
    return (median_font > 0 and block["max_font"] >= median_font * HEADING_FONT_RATIO
            and len(block["texts"][0]) <= MAX_HEADING_CHARS)


def _reconstruct_paragraphs(blocks: list[dict], median_font: float) -> list[dict]:
    """跨块段落重建: 截断行与后续行合并, 标题跨块合并。
    几何事实: 段落首行缩进30pt (x0=107 vs 续行x0=77), 对齐容差取45。"""
    heading_prefix = re.compile(r"^第[一二三四五六七八九十百0-9]+[章节篇]")
    paras: list[dict] = []
    prev_y1 = None
    for b in blocks:
        text = _join_lines(b["texts"])
        heading = _is_heading(b, median_font)
        gap = (b["y0"] - prev_y1) if prev_y1 is not None else 999.0
        prev_y1 = b["y1"]
        if paras:
            last = paras[-1]
            if heading and last["heading"]:
                # 标题续行: 下一标题不以"第X章/节"开头 (如"什么？"续行) 才合并
                is_new_heading = bool(heading_prefix.match(text))
                mergable = not is_new_heading and gap < 60.0
            else:
                body_cont = not last["text"].endswith(tuple(SENT_END))
                mergable = (body_cont and not heading and not last["heading"]
                            and gap < 30.0 and abs(last["x0"] - b["x0"]) < 45.0)
            if mergable:
                last["text"] += text
                last["y1"] = b["y1"]
                continue
        paras.append({"text": text, "heading": heading, "y0": b["y0"],
                      "y1": b["y1"], "x0": b["x0"]})
    return paras


def _split_sentences(text: str) -> list[str]:
    sents = [s.strip().replace("\u3000", "") for s in SENT_SPLIT.split(text)]
    merged: list[str] = []
    for s in sents:
        if not s:
            continue
        if merged and merged[-1][-1] not in SENT_END and s[0] not in "（(【[":
            merged[-1] += s
        else:
            merged.append(s)
    return merged


def build_corpus(pdf_path: Path) -> dict:
    doc = fitz.open(pdf_path)
    all_fonts: list[float] = []
    page_blocks: dict[int, list[dict]] = {}
    for pno, page in enumerate(doc, start=1):
        blocks = _collect_blocks(page.get_text("dict"))
        page_blocks[pno] = blocks
        all_fonts.extend(b["max_font"] for b in blocks if b["max_font"] > 0)
    median_font = statistics.median(all_fonts) if all_fonts else 10.0

    pages_out = []
    for pno in range(1, doc.page_count + 1):
        paras = _reconstruct_paragraphs(page_blocks[pno], median_font)
        paragraphs = []
        for p in paras:
            if p["heading"]:
                continue  # 标题不进语料(章节地图已覆盖)
            sents = [s for s in _split_sentences(p["text"]) if len(s) >= MIN_SENT_LEN]
            if sents:
                paragraphs.append(sents)
        pages_out.append({"page": pno, "paragraphs": paragraphs})
    doc.close()

    n_sent = sum(len(s) for p in pages_out for para in p["paragraphs"] for s in para)
    return {"document": pdf_path.stem, "pages": len(pages_out),
            "sentences": n_sent, "corpus": pages_out}


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(SOURCES_DIR.glob("*.pdf")):
        probe = fitz.open(pdf)
        has_text = any(p.get_text().strip() for p in probe)
        probe.close()
        if not has_text:
            print(f"[corpus] skip (image-only): {pdf.name}", flush=True)
            continue
        print(f"[corpus] {pdf.name}", flush=True)
        c = build_corpus(pdf)
        out = CORPUS_DIR / f"{pdf.stem}.sentences.json"
        out.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[corpus] -> {out}  pages={c['pages']} sentences={c['sentences']}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
