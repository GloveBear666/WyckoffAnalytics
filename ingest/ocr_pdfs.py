# -*- coding: utf-8 -*-
"""
KNOWLEDGE_INGESTION_LAYER - OCR 补充通道 (架构模块1)
====================================================
用途: 处理无文本层的扫描版 PDF (如图片型幻灯片/扫描书)。
流程: 渲染高清页图 -> RapidOCR 识别 -> 带页标记文本落盘。
用法: python ingest/ocr_pdfs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "knowledge" / "sources"
OCR_CACHE = ROOT / "knowledge" / "ocr_pages"
OCR_DIR = ROOT / "knowledge" / "raw_text"

ZOOM = 2.5  # 渲染倍率(72dpi -> 180dpi)


def main() -> None:
    from rapidocr_onnxruntime import RapidOCR

    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    ocr = RapidOCR()
    targets = [p for p in SOURCES_DIR.glob("*.pdf")]
    for pdf in targets:
        doc = fitz.open(pdf)
        has_text = any(p.get_text().strip() for p in doc)
        if has_text:
            print(f"[ocr] skip (has text layer): {pdf.name}", flush=True)
            doc.close()
            continue

        print(f"[ocr] processing: {pdf.name} ({doc.page_count} pages)", flush=True)
        out_lines: list[str] = []
        for pno, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
            img_path = OCR_CACHE / f"{pdf.stem}_p{pno:03d}.png"
            pix.save(img_path)
            result, _ = ocr(str(img_path))
            texts = [line[1] for line in result] if result else []
            out_lines.append(f"\n===== [PAGE {pno}] =====")
            out_lines.extend(texts)
            print(f"[ocr] page {pno}/{doc.page_count}: {len(texts)} lines", flush=True)

        doc.close()
        out_path = OCR_DIR / f"{pdf.stem}.ocr.txt"
        out_path.write_text("\n".join(out_lines), encoding="utf-8")
        print(f"[ocr] done -> {out_path} ({len(out_lines)} lines)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
