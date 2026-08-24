# -*- coding: utf-8 -*-
"""
KNOWLEDGE_MANAGEMENT_LAYER - 知识迭代与追溯 (架构模块6)
========================================================
每次 AI 参数寻优、逻辑修正及回测结果自动生成结构化《学习笔记》:
  - research/learning_notes/<ts>_<topic>.md   (人类可读, 含决策路径)
  - research/learning_notes/notes_index.json   (版本化注册表, 100%可追溯)
记录: 决策路径 / 失效原因 / 优化方向 / 指标快照。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "research" / "learning_notes"
INDEX_PATH = NOTES_DIR / "notes_index.json"


def save_learning_note(topic: str, decision_path: list[str], results: dict,
                       failure_reasons: list[str] | None = None,
                       optimization_direction: list[str] | None = None,
                       version: str = "0.1.0") -> Path:
    """保存一条结构化学习笔记, 返回笔记路径。"""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]", "_", topic)[:40]
    path = NOTES_DIR / f"{ts}_{safe_topic}.md"

    lines = [
        f"# 学习笔记: {topic}",
        "",
        f"- **时间**: {datetime.now().isoformat(timespec='seconds')}",
        f"- **版本**: {version}",
        "",
        "## 决策路径 (Decision Path)",
    ]
    lines += [f"{i+1}. {d}" for i, d in enumerate(decision_path)]
    lines += ["", "## 结果快照 (Results Snapshot)", ""]
    lines += [f"- **{k}**: {v}" for k, v in results.items()]
    if failure_reasons:
        lines += ["", "## 失效原因 (Failure Reasons)", ""]
        lines += [f"- {r}" for r in failure_reasons]
    if optimization_direction:
        lines += ["", "## 优化方向 (Optimization Direction)", ""]
        lines += [f"- {d}" for d in optimization_direction]
    lines += ["", "---", "*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*"]
    path.write_text("\n".join(lines), encoding="utf-8")

    # 更新注册表
    if INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    else:
        index = {"notes": []}
    index["notes"].append({
        "id": path.stem, "topic": topic, "version": version, "created": ts,
        "path": str(path.relative_to(ROOT)),
        "has_failure_reasons": bool(failure_reasons),
    })
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_strategy_log(entry: dict) -> Path:
    """策略版本日志 (research/strategy_log.jsonl): 每次参数寻优/逻辑修正一行。"""
    log = ROOT / "research" / "strategy_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now().isoformat(timespec="seconds")
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return log
