# WyckoffAnalytics — 架构级威科夫量化系统

基于威科夫方法 (Wyckoff Method) 的动态参数化交易系统，覆盖 **US_Equities** 与 **Cryptocurrency** 两个市场。
运行时: Python (pandas/NumPy + Optuna 贝叶斯优化) 为核心沙盒；Web 可视终端 + TradingView Pine Script 为可视化终端。

**GitHub**: https://github.com/GloveBear666/WyckoffAnalytics

## 架构映射

| 模块 | 说明 | 位置 |
|---|---|---|
| 0. CYBORG_QUIZ_LAYER | 试卷盲测答题系统 (随机截取→答题→批改→MFE/MAE标注→错题分析→标注集导出) | `core/quiz.py` `research/quiz/` |
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

# 2. Web 可视终端 (回测 + 温度滑杆 + AI 训练 + 答题评测)
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
- **答题评测页** (Cyborg 第一阶段·试卷盲测): 随机截取 N 根K线盲盒并**隐藏未来走势** → 按威科夫三模块答题 (①强弱度 ②努力与结果 ③盈亏比≥3:1) → 交卷后自动追踪未来 M 根K线批改 (**止损优先**): ❌破止损0分 / ✅达2R目标100分 / ⚠️时间耗尽50分 → 计算 **MFE/MAE** (R 倍数) → 实时错题分析 (画饼率/分模块胜率/观望检验) → 导出**黄金标注集** `[K线矩阵(window,5)] + [人类答案] + [未来真实结果]` 供 AI 训练
- API: `GET /api/status` · `POST /api/backtest` · `POST /api/grid` · `POST /api/train` · `GET /api/train/history` · `POST /api/quiz/new` · `POST /api/quiz/grade` · `GET /api/quiz/stats` · `POST /api/quiz/export` · `GET /api/quiz/labels/<file>`

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

## 部署与多端访问 (v0.3.5, Vercel)

**架构**: 静态前端托管在 **Vercel** (https://wyckoff-analytics.vercel.app, 由 GitHub 仓库自动发布)；后端 Flask 跑在你的电脑上 (`0.0.0.0:8088`, 已启用 CORS)。前端顶部"后端地址"输入框把任意客户端指向你的后端。

### 1. 前端发布 (已配置: GitHub → Vercel 自动部署)

- 线上地址: **https://wyckoff-analytics.vercel.app**
- 每次 `git push` 到 main, GitHub Actions (`deploy-vercel.yml`) 自动部署生产环境
- 部署所需的 `VERCEL_TOKEN/VERCEL_ORG_ID/VERCEL_PROJECT_ID` 已存入仓库 Secrets (不会出现在代码中)
- 重新接入/换账号: Vercel → Add New → Project → Import 本仓库 → Framework **Other** · Root Directory **`web/static`** → Deploy

### 2. 本机启动后端

```bash
python web/app.py          # 默认绑定 0.0.0.0:8088, 启动时打印局域网地址 http://<本机IP>:8088
# 只允许本机: HOST=127.0.0.1 python web/app.py
```

### 3. 客户端访问方式（可同时使用）

| 方式 | 地址 | 适用场景 |
|---|---|---|
| 🖥 本机 | `http://127.0.0.1:8088` | 桌面浏览器 |
| 📶 局域网 | `http://<本机IP>:8088` (如 192.168.x.x) | 同一 WiFi 下的手机/平板/另一台电脑 |
| 🌐 公网 | Vercel 页面 + 后端隧道 | 任意网络环境 |

**公网访问（二选一）**:

```bash
# 方式A: cloudflared 临时隧道 (免费, 无需注册, 每次运行URL会变)
cloudflared tunnel --url http://127.0.0.1:8088
# → 得到 https://xxx.trycloudflare.com, 填入前端"后端地址"即可

# 方式B: Tailscale (免费, 稳定HTTPS域名, 推荐长期使用)
# 在本机与各客户端安装 Tailscale 并登录同一账号后:
tailscale serve --bg 8088   # 或 tailscale serve https / http://127.0.0.1:8088
# → 得到 https://<机器名>.<tailnet>.ts.net (永久HTTPS地址)
```

> ⚠️ **混合内容限制**: 网页是 https 时, 后端也必须是 https (用 cloudflared/Tailscale 隧道), 浏览器会拦截 http 混入。局域网方式请直接访问 `http://<IP>:8088` (同源, 无此限制)。
> ⚠️ **Windows 防火墙**: 局域网/公网访问需放行端口: 管理员 PowerShell 执行
> `netsh advfirewall firewall add rule name="wyckoff-web" dir=in action=allow protocol=TCP localport=8088`

### 4. 家庭服务器 24×7 (Mac mini / Linux + Docker)

后端无需留在某台电脑上: 仓库已内置 **Dockerfile + docker-compose.yml** (持久卷挂载 `data/` 与 `research/`, 开机自启), 部署到家里的 Mac mini 即可让电脑关机、服务永续:

```bash
git clone https://github.com/GloveBear666/WyckoffAnalytics.git && cd WyckoffAnalytics
bash scripts/macmini_deploy.sh    # 自动 pull + 构建 + 启动 + 健康检查
```

完整指南: [`docs/DEPLOY_MACMINI.md`](docs/DEPLOY_MACMINI.md) · 多设备 GitHub 协作: [`docs/GITHUB_MULTIDEVICE.md`](docs/GITHUB_MULTIDEVICE.md)

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
- `knowledge/factors/concept_windows_v2.json` — **句子级**概念窗口 (22 概念 × 15 窗, 整句匹配/整句窗口/去重/TOC过滤; 语料构建: `ingest/extract_sentences.py` → `ingest/extract_concepts_v2.py`)
- `research/learning_notes/` — 每次寻优/回测自动生成学习笔记
- `research/training_log.json` — AI 训练轮次历史 (每轮参数/准确率/验证判定)
- `research/strategy_log.jsonl` — 策略版本日志
