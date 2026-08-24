# WyckoffAnalytics — 架构级威科夫量化系统

基于威科夫方法 (Wyckoff Method) 的动态参数化交易系统，覆盖 **US_Equities** 与 **Cryptocurrency** 两个市场。
运行时: Python (pandas/NumPy + Optuna 贝叶斯优化) 为核心沙盒；Web 可视终端 + TradingView Pine Script 为可视化终端。

**GitHub**: https://github.com/GloveBear666/WyckoffAnalytics

## 架构映射

| 模块 | 说明 | 位置 |
|---|---|---|
| 1. KNOWLEDGE_INGESTION_LAYER | PDF文本提取/章节地图/概念窗口/OCR | `ingest/` `knowledge/` |
| 2. MARKET_ISOLATION_LAYER | 美股RTH(跳空过滤) / 加密7x24(插针容错) | `config/market_profiles.json` `core/data.py` |
| 3. EXECUTION_ENGINE | 温度控制 T∈[0.1,1.0] 全参数插值 + HTF多周期确认 | `core/signals.py` `core/indicators.py` |
| 4. AI_OPTIMIZATION_AND_BACKTESTING | 摩擦模型 + Optuna 贝叶斯优化 (Calmar/Sharpe) | `core/backtest.py` `core/optimizer.py` `core/training.py` |
| 5. VALIDATION_CONSTRAINTS | Walk-Forward + OOS + 衰减率>30%自动否决 | `validation/walk_forward.py` |
| 6. KNOWLEDGE_MANAGEMENT_LAYER | 学习笔记/训练历史/策略日志 (可追溯) | `core/knowledge.py` `research/` |

## 快速开始 (Windows / macOS)

```bash
# 0. 环境 (首次)
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 1. 数据抓取 (真实行情, 缓存到 data/)
python core/data.py --profile crypto --symbol BTC/USDT --tf 1h 4h 1d
python core/data.py --profile equity --symbol SPY AAPL

# 2. Web 可视终端 (回测 + 温度滑杆 + AI 训练)
python web/app.py          # -> http://127.0.0.1:8088

# 3. 端到端流水线: 回测 -> 贝叶斯优化 -> Walk-Forward -> 学习笔记
python scripts/run_pipeline.py --symbol BTC/USDT --profile crypto --tf 4h --htf-tf 1d --trials 40
python scripts/run_pipeline.py --symbol SPY  --profile equity --trials 40

# 4. 命令行 AI 训练 (多轮迭代, 历史在 research/training_log.json)
python core/training.py --symbol BTC/USDT --profile crypto --tf 4h --htf-tf 1d --trials 30

# 5. 冒烟测试 (合成数据)
python scripts/smoke_test.py
```

## Web 可视终端 (本地 AI 训练台)

- **回测页**: 温度滑杆 T∈[0.1,1.0] 实时联动全部插值参数；标的/周期/HTF确认/窗口/持有/冷却可调；净值曲线+回撤图+交易明细；温度扫描对比表
- **AI 训练页**: 一键本地训练 —— 贝叶斯优化(真实历史数据) → 全量回测 → **准确率统计**(整体胜率+分设置胜率) → Walk-Forward 样本外验证(衰减>30%自动否决) → 写入训练历史；历史面板显示每轮 适应度/准确率/判定，并标记**当前最优轮次**（最高 OOS Calmar）
- API: `GET /api/status` · `POST /api/backtest` · `POST /api/grid` · `POST /api/train` · `GET /api/train/history`

## 温度控制语义 (模块3核心)

- **T = 0.1 低容忍**: 多因子共振(≥3) 才触发, 止损 0.5 ATR, 盈亏比 3.0, 仓位 5%, 适用于高波动/不明朗市场
- **T = 1.0 高容忍**: 单因子突破即触发, 止损 2.0 ATR, 盈亏比 1.5, 仓位 25%, 适用于强趋势市场
- 中间值全参数线性插值 (`config/temperature.json`), T 由环境动态输入

## 多周期确认 (HTF, v0.2)

- 高层级时间框架的趋势/吸筹/派发评分 + 近期 SC/Spring 事件，`merge_asof` 无前视对齐后作为入场门控
- 实测: BTC 4h+1d HTF 使 Walk-Forward 从"否决"(1h 单周期, OOS 衰减112%) 转为 **PASSED** (全部折 OOS Calmar ≥ 1.07)

## 验证协议 (模块5)

- 步进分析: 4折 Walk-Forward, 每折 样本内优化 → 样本外检验
- **否决规则**: OOS 相对 IS 衰减率 (Calmar/Sharpe) > 30% 且 OOS 表现不佳 → 系统自动否决

## 在 Mac 上开始 (fork 后)

```bash
git clone https://github.com/GloveBear666/WyckoffAnalytics.git   # 或 GitHub 页面点 Fork
cd WyckoffAnalytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python core/data.py --profile crypto --symbol BTC/USDT --tf 4h 1d   # 抓取数据
python web/app.py                                                    # 打开 http://127.0.0.1:8088
```

> 注: 书籍 PDF 源文件与提取全文受版权保护未入库 (`knowledge/sources/`, `knowledge/raw_text/` 已在 .gitignore)。
> 因子矩阵/章节地图/全部代码/研究记录均在仓库内。数据可随时重新抓取。

## 知识溯源

- `knowledge/factors/factor_matrix_v0.1.json` — 确定性量化因子矩阵 (含页码溯源: 孟洪涛《威科夫操盘法》2016 + Wyckoff Analytics 官方课件)
- `knowledge/factors/concept_windows.json` — 22 概念 × 249 原文窗口
- `research/learning_notes/` — 每次寻优/回测自动生成学习笔记
- `research/training_log.json` — AI 训练轮次历史 (每轮参数/准确率/验证判定)
- `research/strategy_log.jsonl` — 策略版本日志
