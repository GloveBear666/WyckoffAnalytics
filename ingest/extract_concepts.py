# -*- coding: utf-8 -*-
"""
KNOWLEDGE_INGESTION_LAYER - 概念窗口提取器 (架构模块1)
======================================================
对核心威科夫术语做段落窗口提取, 生成事实锚定 JSON:
  knowledge/factors/concept_windows.json
每个概念: {term, pages:[{page, window_text}]}
窗口 = 命中行 ± 上下文行数。
用法: python ingest/extract_concepts.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "knowledge" / "raw_text" / "威科夫操盘法.txt"
OUT = ROOT / "knowledge" / "factors" / "concept_windows.json"

# 核心概念术语 -> 量化因子锚点 (覆盖六章全部关键概念)
CONCEPTS = {
    "供求关系": ["供求", "需求大于供应", "供应大于需求", "需求扩大", "供应扩大"],
    "因果": ["因果关系", "因", "果", "准备过程"],
    "努力结果": ["努力", "结果", "放量滞涨", "放量不涨", "量增价不涨"],
    "抢购高潮": ["抢购高潮", "BC", "高潮"],
    "停止行为": ["停止行为", "停止", "stopping"],
    "恐慌抛售": ["恐慌抛售", "抛售高潮", "SC"],
    "自动反弹": ["自动反弹", "AR"],
    "二次测试": ["二次测试", "ST", "测试"],
    "吸筹": ["吸筹", "建仓", "派发区", "吸筹区"],
    "震仓": ["震仓", "shakeout", "震仓"],
    "派发": ["派发", "出货", "派发区"],
    "spring": ["Spring", "spring", "弹簧", "弹簧效应"],
    "上冲": ["上冲", "Upthrust", "UT", "诱多"],
    "sos": ["SOS", "强势出现", "需求进入"],
    "sow": ["SOW", "弱势出现", "供应进入"],
    "突破": ["突破", "阻力突破", "支撑跌破"],
    "支撑阻力": ["支撑", "阻力", "交易区间", "TR"],
    "量价": ["成交量", "量能", "振幅", "价差范围"],
    "危机管理": ["危机管理", "止损", "仓位", "风险"],
    "看盘顺序": ["看盘顺序", "看盘步骤"],
    "CM原则": ["聪明钱", "主力", "CM", "机构"],
    "趋势": ["趋势", "牛市", "熊市", "上升趋势", "下降趋势"],
}

CTX_BEFORE, CTX_AFTER = 2, 3  # 窗口上下文行数


def main() -> None:
    text = RAW.read_text(encoding="utf-8")
    pages = text.split("===== [PAGE ")[1:]
    page_lines: dict[int, list[str]] = {}
    for chunk in pages:
        pno = int(chunk.split("]")[0])
        body = chunk.split("] =====", 1)[1]
        page_lines[pno] = [ln.strip() for ln in body.splitlines() if ln.strip()]

    out: dict[str, list[dict]] = {}
    for concept, terms in CONCEPTS.items():
        hits: list[dict] = []
        for pno in sorted(page_lines):
            lines = page_lines[pno]
            for i, ln in enumerate(lines):
                if any(t in ln for t in terms):
                    lo, hi = max(0, i - CTX_BEFORE), min(len(lines), i + CTX_AFTER)
                    window = lines[lo:hi]
                    hits.append({"page": pno, "window": window})
        out[concept] = hits[:12]  # 每概念最多12个窗口
        print(f"[concepts] {concept}: {len(hits)} windows -> kept {len(out[concept])}", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[concepts] -> {OUT}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
