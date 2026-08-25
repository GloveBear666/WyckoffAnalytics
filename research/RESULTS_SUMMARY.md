# WyckoffAnalytics — 系统状态与回测结果总报告

> 更新: 2026-08-25 (v0.3.4: 多端部署 GitHub Pages) | 所有结果含完整摩擦模型（手续费+滑点+价差）

## 0. 新增能力

- **v0.3.4 多端部署**: 前端托管 GitHub Pages (`https://glovebear666.github.io/WyckoffAnalytics/`, Actions 自动部署) + 后端 CORS/0.0.0.0 多客户端访问 (局域网/cloudflared/Tailscale 隧道, 详见 README「部署与多端访问」)

- **v0.3.3 答题评测系统** (Cyborg 第一阶段·试卷盲测, Web 页签): 见 §8
- **v0.3 本地 AI 训练台** (Web): `POST /api/train` — 贝叶斯优化 → 全量回测 → **准确率统计**（整体胜率 + 分进场设置胜率）→ Walk-Forward 样本外验证 → 训练历史 `research/training_log.json`（含当前最优轮次标记）；CLI: `python core/training.py`
- 实测: Web API 首轮训练 BTC 4h+1dHTF → 适应度 0.744, 准确率 65.55%, 验证未否决 ✅
- **GitHub**: https://github.com/GloveBear666/WyckoffAnalytics (PUBLIC, main) — 含 .gitignore/.gitattributes 跨平台换行、macOS 字体支持、Mac fork 安装指引; 版权 PDF 与提取全文不入库

## 1. 知识提取层 (模块1) — 完成

| 源文件 | 类型 | 提取结果 |
|---|---|---|
| 威科夫操盘法.pdf (孟洪涛, 284页) | 文本层 | 114,467 字符; 1,534 标题候选; 6章完整章节地图 |
| wyckoff-analytics-mandarin-v2.pdf (Wyckoff Analytics 官方课件, 15页) | 扫描图片 | RapidOCR 616行; 五步法/三大定律/价格周期/九大检验/派发事件标注 |

- **因子矩阵**: `knowledge/factors/factor_matrix_v0.1.json` — 22 个确定性量化因子（9 基础量价 + 16 事件 + 6 结构 + 3 组合），每个因子含公式、输出域、原文页码溯源
- **概念锚点**: `knowledge/factors/concept_windows_v2.json` — 句子级语料(2,787 完整句)重建后提取: 22 概念 × 15 整句窗口, 短语级匹配/去重/TOC过滤 (v0.1 行级版本语义破碎, 已归档为 `concept_windows_v0.1.legacy.json`)

## 2. 市场隔离层 (模块2) — 完成

- `config/market_profiles.json`: CRYPTO_PROFILE (7x24, 滑点12bps+价差8bps+费率10bps) / US_EQUITY_PROFILE (RTH, 跳空缺口>1.5*ATR 过滤)
- 数据缓存: BTC/USDT 1h(17,520) · 4h(4,380) · 1d 5年(1,825) | SPY/AAPL 日线各 1,506 — `data/`

## 3. 执行引擎与温度控制 (模块3) — 完成 (v0.2 新增 HTF)

- `core/indicators.py` + `core/signals.py`: 温度 T∈[0.1,1.0] 全参数线性插值
- **v0.2 多周期确认 (HTF)**: `htf_context()` — 高层级时间框架的趋势/吸筹/派发评分 + 近期 SC/Spring 事件，`merge_asof` 无前视对齐，作为入场门控并计入共振因子。验证: 1h 信号 911→703 (过滤22%)
- Pine Script 终端: `pine/wyckoff_events_v0.1.pine`

## 4. AI优化与回测 (模块4) — 完成

- Optuna TPE 贝叶斯优化, fitness = 0.6·tanh(Calmar/2)+0.4·tanh(Sharpe/2); t+1开盘成交/止损止盈/日熔断/冷却/跳空过滤

## 5. 强制验证协议 (模块5) — v0.2 结果

4 折 Walk-Forward; 衰减率 > 30% 且 OOS Calmar < 0.5 → 自动否决:

| 标的 | 配置 | 最优参数 | IS→OOS Calmar | 判定 |
|---|---|---|---|---|
| **BTC 4h** | **+1d HTF确认** | T=0.46, win=65, hold=60 | 1.78 → **1.07/2.65/1.21** (fold2衰减2%) | ✅ **PASSED** |
| SPY 1d | 单周期 | T=0.19, win=75, hold=70 | 1.34 → 1.04 (衰减22%) | ✅ PASSED |
| BTC 1h | 单周期 (v0.1) | T=0.46, win=90 | 0.33 → -0.04 (衰减112%) | ❌ REJECTED |
| BTC 1d | 单周期 | T=0.96, win=60 | 1.27 → 0.00 (fold2) | ❌ REJECTED (交易过稀: 5年仅26笔) |
| AAPL 1d | 单周期 | T=0.92, win=70 | 1.86 → -0.67 (衰减136%) | ❌ REJECTED |

**BTC 4h+1dHTF 通过策略 (摩擦后, 2年4h线)**: 收益 +39.6%, CAGR 2.82%, Sharpe 1.83, Calmar 1.78, MaxDD -1.58%, 204笔, 胜率 66.7%, 盈亏比 2.96
净值曲线: `research/backtests/BTC_4h_equity_curve.png` · SPY: `research/backtests/SPY_equity_curve.png`

> **v0.2 迭代结论**: HTF 多周期确认是 BTC 从"否决"到"通过"的关键——1h 单周期 fold1 衰减 112% → 4h+1d HTF 全部折 OOS Calmar ≥ 1.07。1d 单周期因交易过于稀疏(5年26笔, 每折~6笔)统计意义不足被否决, 属数据频率问题而非逻辑缺陷。

## 6. Web 可视终端 — 已上线

**访问: http://127.0.0.1:8088** (启动: `python web/app.py`)

- **温度滑杆 T∈[0.1,1.0]**: 实时联动显示插值参数（共振下限/止损ATR/盈亏比/仓位/日熔断/趋势质量/量能门槛）
- **一键回测**: 标的选择(缓存数据集) + 周期 + HTF确认 + 区间窗口/最大持有/入场冷却 → 净值曲线/回撤图/指标卡片/交易明细/信号统计
- **温度扫描**: T∈{0.1,0.3,0.5,0.7,1.0} 全量回测对比表（当前T高亮）
- 架构: Flask (`web/app.py`) + 无依赖单页前端 (`web/static/index.html`)，Canvas 自绘图表
- API: `GET /api/status` · `POST /api/backtest` · `POST /api/grid` · `GET /api/temperature?T=`

## 7. 知识管理 (模块6) — 完成

- 学习笔记: `research/learning_notes/` (7篇) · 策略日志: `research/strategy_log.jsonl` · 验证报告: `research/validation/walk_forward_*.json` (5份, 按标的+周期命名)

## 8. 答题评测系统 (Cyborg 第一阶段) — v0.3.3 上线

**入口**: Web 终端「答题评测」页签 · 核心: `core/quiz.py` · 数据: `research/quiz/`

闭环流程: **随机截取盲盒**(默认 120×4H K线, 隐藏未来走势) → **三模块答题** → **自动批改**(未来60根, 止损优先) → **MFE/MAE 标注** → **错题分析** → **黄金标注集导出**

| 环节 | 实现 |
|---|---|
| 盲盒生成 | 随机起点(会话内去重), 进场价=可见区最后收盘, 建议止损=近20根极值∓0.5×ATR(可改), 载荷不下发未来数据 |
| 模块1 强弱度 | A绝对强势/B相对强势(→做多) · C混沌(→观望) · D绝对弱势(→做空) |
| 模块2 努力结果 | A无量空跌/B巨量不跌/C无量反弹/D放量滞涨 (最右端3根, 作为信号标签记录) |
| 模块3 盈亏比 | A是(SL→TP≥3:1, 交易) / B否(放弃, 记录"如果入场"潜在结果检验克制) |
| 自动批改 | ❌破止损 **0分** (止损优先, 跳空按开盘价成交) · ✅达2R **100分** · ⚠️60根耗尽 **50分** |
| 标注矩阵 | MFE/MAE 以 R 倍数记录(含出场当根极值), MAE 同时给占止损距离百分比 |
| 错题分析 | 分模块胜率/均分 · **画饼率**(看对方向却被止损) · 观望检验(双向均无2R=正确) · 错题榜 |
| 标注导出 | `research/quiz/labels/quiz_labels_*.jsonl`: `[K线矩阵(window,5)] + [人类答案] + [未来真实结果]` |

- 冒烟测试: `scripts/quiz_smoke.py` — 做多/做空/观望/盈亏比放弃全路径 + 批改数学断言(TARGET→MFE≥2R, STOP→MAE≥1R) + 未来数据零泄露校验
- 实测样本: BTC 4h 一轮 15 题 → 平均分 27.8, 完美率 22.2%, 止损率 66.7% (纯随机盲答, 供流程验证, 不具统计意义)
- API: `POST /api/quiz/new` · `POST /api/quiz/grade` · `GET /api/quiz/stats` · `POST /api/quiz/export` · `GET /api/quiz/labels/<file>`

## 迭代路线 (v0.4 候选)

1. **BTC 1d**: 交易过稀 → 降低共振门槛或改 1d+1w HTF; 或直接采用 4h+1d 作为主配置
2. **AAPL**: fold1 OOS 失效 → 波动率带收窄、相对强度过滤
3. **优化器已知项**: `vol_z_min` trial 参数尚未接入 `generate_signals` (当前由 T 插值决定量能门槛) — 待接线
4. 摩擦敏感性压力测试 (滑点×2) · P&F 点数图目标计量

## 复现命令

```bash
python scripts/run_pipeline.py --symbol BTC/USDT --profile crypto --tf 4h --htf-tf 1d --trials 40
python scripts/run_pipeline.py --symbol BTC/USDT --profile crypto --tf 1d --trials 40 --min-trades 10
python scripts/run_pipeline.py --symbol SPY  --profile equity --trials 40
python web/app.py   # Web可视终端
```
