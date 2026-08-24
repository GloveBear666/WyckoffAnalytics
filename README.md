# WyckoffAnalytics — 架构级威科夫量化系统

基于威科夫方法 (Wyckoff Method) 的动态参数化交易系统，覆盖 **US_Equities** 与 **Cryptocurrency** 两个市场。
运行时: Python (pandas/NumPy + Optuna 贝叶斯优化) 为核心沙盒；可视化终端为 TradingView (Pine Script，待生成)。

## 架构映射

| 模块 | 说明 | 位置 |
|---|---|---|
| 1. KNOWLEDGE_INGESTION_LAYER | PDF文本提取/章节地图/概念窗口/OCR | `ingest/` `knowledge/` |
| 2. MARKET_ISOLATION_LAYER | 美股RTH(跳空过滤) / 加密7x24(插针容错) | `config/market_profiles.json` `core/data.py` |
| 3. EXECUTION_ENGINE | 温度控制 T∈[0.1,1.0] 全参数插值 | `core/signals.py` `core/indicators.py` |
| 4. AI_OPTIMIZATION_AND_BACKTESTING | 摩擦模型 + Optuna 贝叶斯优化 (Calmar/Sharpe) | `core/backtest.py` `core/optimizer.py` |
| 5. VALIDATION_CONSTRAINTS | Walk-Forward + OOS + 衰减率>30%自动否决 | `validation/walk_forward.py` |
| 6. KNOWLEDGE_MANAGEMENT_LAYER | 学习笔记/策略日志 (Markdown+JSON, 可追溯) | `core/knowledge.py` `research/` |

## 快速开始

```bash
# 1. 知识提取 (已执行, 可重跑)
python ingest/extract_pdfs.py          # 文本层PDF -> raw_text + 章节地图
python ingest/ocr_pdfs.py              # 扫描版PDF -> OCR文本
python ingest/extract_concepts.py      # 核心概念窗口 -> factor matrix 锚点

# 2. 数据
python core/data.py --profile crypto --symbol BTC/USDT --tf 1h
python core/data.py --profile equity --symbol SPY AAPL

# 3. 冒烟测试 (合成数据)
python scripts/smoke_test.py

# 4. 端到端流水线: 回测 -> 贝叶斯优化 -> Walk-Forward -> 学习笔记
python scripts/run_pipeline.py --symbol BTC/USDT --profile crypto --tf 1h --trials 40
python scripts/run_pipeline.py --symbol SPY --profile equity --trials 40
```

## 温度控制语义 (模块3核心)

- **T = 0.1 低容忍**: 多因子共振(≥3) 才触发, 止损 0.5 ATR, 盈亏比 3.0, 仓位 5%, 适用于高波动/不明朗市场
- **T = 1.0 高容忍**: 单因子突破即触发, 止损 2.0 ATR, 盈亏比 1.5, 仓位 25%, 适用于强趋势市场
- 中间值全参数线性插值 (`config/temperature.json`), T 由环境动态输入

## 验证协议 (模块5)

- 步进分析: 4折 Walk-Forward, 每折 样本内优化 → 样本外检验
- **否决规则**: OOS 相对 IS 衰减率 (Calmar/Sharpe) > 30% 且 OOS 表现不佳 → 系统自动否决

## 知识溯源

- `knowledge/factors/factor_matrix_v0.1.json` — 确定性量化因子矩阵 (含页码溯源: 孟洪涛《威科夫操盘法》2016 + Wyckoff Analytics 官方课件)
- `knowledge/factors/concept_windows.json` — 22 概念 × 249 原文窗口
- `research/learning_notes/` — 每次寻优/回测自动生成学习笔记
- `research/strategy_log.jsonl` — 策略版本日志
