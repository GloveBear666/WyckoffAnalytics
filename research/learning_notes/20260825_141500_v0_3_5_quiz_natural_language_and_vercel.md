# 学习笔记: v0.3.5_quiz_natural_language_and_vercel

- **时间**: 2026-08-25T14:15:00
- **版本**: 0.3.5
- **依据文档**: Cyborg_Trading_System_Summary.md + 用户规范文本

## 决策路径 (Decision Path)
1. 用户提供三问自然语言规范, 逐字对齐重构题库:
   - Q1 背景趋势界定: A吸筹末期 / B趋势中继 / C无序震荡 / D顶部派发 (方向映射不变: A/B→多, C→观望, D→空)
   - Q2 右侧量价验证: A供应测试(无量回落) / B被动吸收(巨量承接) / C需求枯竭(无量上行) / D派发受阻(放量滞涨)
   - Q3 盈亏空间测算: A结构成立(SL→TP≥3:1) / B结构否定(赔率受限)
2. 兼容性: 记录仅存字母码 (A/B/C/D), 题库文本可自由迭代, 历史记录无需迁移
3. 导出增强: 每条标注附 outcome.label + explanation (成绩说明); 同步生成 *.report.md 报告 (评分规则/成绩汇总/分模块画饼率/认知漏洞检测/结论)
4. 新增重置: POST /api/quiz/reset 清空记录与进行中题目, 导出文件保留为档案
5. 发布策略: GitHub Pages → Vercel (vercel.json + Root Directory=web/static 一键导入, push 自动部署)

## 结果快照 (Results Snapshot)

- 冒烟测试全通过: 自然语言题库断言 + 报告章节 (评分规则/成绩汇总/背景趋势界定/右侧量价验证/认知检验/结论) + 重置归零
- 端到端: grade 返回新题库结局; export 生成 labels + report.md; reset cleared=10 (用户积累记录) 后统计归零
- 真实记录: 用户已通过网页完成 10 条答题 (交易5/观望放弃5) — 答题闭环已在真实使用

## 优化方向 (Optimization Direction)

- Vercel 接入后: 更新 README 部署段, 删除 Pages workflow (二选一)
- 认知漏洞检测的统计门槛 (每选项 ≥3 笔) 随数据积累自然激活
- 标注集规模达到数百条后: 训练 CNN/LSTM 模式识别 (Summary 第三章)

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*
