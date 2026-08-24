# -*- coding: utf-8 -*-
"""
KNOWLEDGE_INGESTION_LAYER - 概念窗口提取器 v2 (语义级)
======================================================
基于句子级语料 (extract_sentences.py 输出), 修复 v0.1 行级切割的语义破碎:
  - 整句匹配: 术语必须完整出现在句子内 (短语级正则, 最长优先)
  - 整句窗口: 命中句 ± 同段前后句 (语义完整, 无残句)
  - 去重: 同页同段同句只保留一次
  - TOC 过滤: 章节列表页/行不进入窗口
输出: knowledge/factors/concept_windows_v2.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "knowledge" / "raw_text" / "威科夫操盘法.sentences.json"
OUT = ROOT / "knowledge" / "factors" / "concept_windows_v2.json"

# 术语表 v2: 短语级 (最长优先自动排序), 覆盖六章核心概念
CONCEPTS_V2 = {
    "供求关系": ["供不应求", "供过于求", "需求大于供应", "供应大于需求", "供求关系",
                "需求扩大", "供应扩大", "供求平衡", "买压", "卖压"],
    "因果关系": ["因果关系", "准备过程", "因果"],
    "努力结果": ["努力和结果的关系", "努力没有结果", "努力和结果", "努力与结果",
                "努力和效果", "放量滞涨", "放量滞跌", "努力和结果"],
    "抢购高潮": ["抢购高潮", "购买高潮", "买入密集区"],
    "停止行为": ["停止行为"],
    "恐慌抛售": ["恐慌抛售", "超卖高潮", "抛售高潮"],
    "自动反弹": ["自动反弹", "自然反弹"],
    "二次测试": ["二次测试", "成功的二次测试", "测试蜡烛", "测试过程"],
    "吸筹": ["吸筹过程", "吸筹结束", "吸筹区", "吸筹", "建仓", "收购股票",
            "收集筹码", "垂直需求柱"],
    "震仓": ["终极震仓", "普通震仓", "震仓"],
    "派发": ["派发过程", "派发区", "派发", "出货", "清仓", "垂直供应柱"],
    "spring": ["弹簧效应", "下冲反弹", "弹簧"],
    "上冲": ["上冲回落", "上冲"],
    "sos": ["强势出现", "跃过小溪", "SOS"],
    "sow": ["弱势出现", "熊市初显", "最后供应点", "SOW"],
    "突破": ["突破", "冰线", "阻力突破", "支撑跌破"],
    "支撑阻力": ["交易区间", "阻力线", "支撑线", "支撑区", "阻力区", "死角",
                "支撑", "阻力"],
    "量价": ["成交量", "振幅", "价差", "量价", "走势速度"],
    "危机管理": ["危机管理", "止损", "仓位", "资金管理", "风险"],
    "看盘顺序": ["看盘顺序", "看盘步骤", "看图顺序"],
    "CM原则": ["聪明钱", "主力机构", "综合人", "操纵者", "大资金", "CM"],
    "趋势": ["上升趋势", "下降趋势", "上涨趋势", "牛市", "熊市", "价格周期",
            "趋势", "MarkUp", "MarkDown"],
}

WINDOW_BEFORE, WINDOW_AFTER = 1, 1   # 命中句前后各1句
MAX_WINDOWS_PER_CONCEPT = 15
TOC_LINE = re.compile(r"^第[一二三四五六七八九十百0-9]+[章节篇]")


def _compile_terms(terms: list[str]) -> re.Pattern:
    """最长优先交替模式, 大小写不敏感。"""
    ordered = sorted(terms, key=len, reverse=True)
    parts = [re.escape(t) for t in ordered]
    return re.compile("|".join(parts), re.IGNORECASE)


def _is_toc_paragraph(sents: list[str]) -> bool:
    """目录行判定: 过半句子匹配 第X章/节 或为纯数字/页码。"""
    if not sents:
        return True
    hits = sum(1 for s in sents if TOC_LINE.match(s.strip()) or re.fullmatch(r"[\d\s.]+", s.strip()))
    return hits > len(sents) / 2


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    stats: dict[str, dict] = {}
    for concept, terms in CONCEPTS_V2.items():
        pat = _compile_terms(terms)
        windows: list[dict] = []
        seen: set = set()
        for page in corpus["corpus"]:
            for pidx, para in enumerate(page["paragraphs"]):
                if _is_toc_paragraph(para):
                    continue
                for sidx, sent in enumerate(para):
                    if not pat.search(sent):
                        continue
                    key = (page["page"], pidx, sidx)
                    if key in seen:
                        continue
                    seen.add(key)
                    lo = max(0, sidx - WINDOW_BEFORE)
                    hi = min(len(para), sidx + WINDOW_AFTER + 1)
                    windows.append({
                        "page": page["page"],
                        "paragraph": pidx,
                        "sentence": sidx,
                        "window": para[lo:hi],
                    })
                    if len(windows) >= MAX_WINDOWS_PER_CONCEPT:
                        break
                if len(windows) >= MAX_WINDOWS_PER_CONCEPT:
                    break
            if len(windows) >= MAX_WINDOWS_PER_CONCEPT:
                break
        out[concept] = windows
        stats[concept] = {"terms": len(terms), "windows": len(windows),
                          "pages": sorted({w["page"] for w in windows})[:8]}
        print(f"[concepts-v2] {concept}: {len(windows)} windows "
              f"pages={stats[concept]['pages']}", flush=True)

    OUT.write_text(json.dumps({"version": "0.2", "window_before": WINDOW_BEFORE,
                               "window_after": WINDOW_AFTER, "concepts": out,
                               "stats": stats},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[concepts-v2] -> {OUT}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
