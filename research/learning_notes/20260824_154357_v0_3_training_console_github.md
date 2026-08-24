# 学习笔记: v0.3_training_console_github

- **时间**: 2026-08-24T15:43:57
- **版本**: 0.3.0

## 决策路径 (Decision Path)
1. 修复前端 v.startsWith 报错 (m.trades 数字类型 -> String())
2. 新增本地AI训练台: /api/train = 贝叶斯优化+全量回测+准确率统计(分设置胜率)+Walk-Forward+历史记录
3. Web验证: 首轮训练 BTC 4h+1dHTF 适应度0.744 准确率65.55% 未否决
4. git init + .gitignore(版权PDF/全文/数据缓存排除) + .gitattributes(LF) + 跨平台字体(plotutils)
5. gh repo create -> https://github.com/GloveBear666/WyckoffAnalytics 推送完成

## 结果快照 (Results Snapshot)

- **web_train_round1**: {'fitness': 0.744, 'accuracy': 0.6555, 'vetoed': False}
- **github**: https://github.com/GloveBear666/WyckoffAnalytics

## 优化方向 (Optimization Direction)

- Mac 上 fork 后直接训练: clone + venv + pip install -r requirements.txt
- 训练历史将不断累积, 自动标记最高 OOS Calmar 轮次

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*