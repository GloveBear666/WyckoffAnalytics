# 学习笔记: v0.3.2_semantic_concept_windows

- **时间**: 2026-08-24T15:55:36
- **版本**: 0.3.2

## 决策路径 (Decision Path)
1. 用户反馈: concept_windows.json 解析不正确, 语义破碎
2. 根因1: 行级窗口 - 中文句被PDF行尾截断 (供不应+求, 窗口以残句开头)
3. 根因2: 同句以行偏移重复出现在多个窗口
4. 根因3: TOC页(15-16)目录行污染窗口
5. 根因4: 术语单字匹配 (因/果) 导致大量无关窗口
6. 修复: 句子级语料重建(extract_sentences.py) - 块阅读顺序+字体识别标题+跨块段落重建(缩进容差45pt)+标点分句
7. v2提取(extract_concepts_v2.py): 短语级最长优先正则, 命中句±1句窗口, 去重, TOC过滤

## 结果快照 (Results Snapshot)

- **corpus**: {'sentences': 2787, 'mean_len': 36.6}
- **windows_v2**: {'concepts': 22, 'per_concept': 15, 'audit_bad_ratio': '2.8% (格式伪影)'}

## 优化方向 (Optimization Direction)

- 术语表按章节精化
- OCR课件语料接入同一句子级管线

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*