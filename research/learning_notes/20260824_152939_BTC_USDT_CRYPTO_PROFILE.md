# 学习笔记: BTC/USDT_CRYPTO_PROFILE

- **时间**: 2026-08-24T15:29:39
- **版本**: 0.1.0

## 决策路径 (Decision Path)
1. 知识提取: 主教材(284页,114k字符) + 课件OCR(15页) -> 因子矩阵 v0.1 (18个基础/事件/结构因子)
2. 温度参数 T∈[0.1,1.0] 线性插值: 共振数/止损/盈亏比/仓位
3. 贝叶斯优化 40 trials -> 最优参数 {'T': 0.45834538759536636, 'feature_window': 65, 'max_bars_hold': 60, 'vol_z_min': 0.7448917392631468}
4. Walk-Forward 4 折: 验证结果 PASSED

## 结果快照 (Results Snapshot)

- **grid**: {'T0.1': {'total_return': 0.03395584803634155, 'sharpe': 0.8653761627846323, 'calmar': 0.8731679509192132, 'max_drawdown': -0.0031913083193650937, 'trades': 116}, 'T0.3': {'total_return': 0.19370851867993166, 'sharpe': 1.6406403218077277, 'calmar': 1.5252708135028652, 'max_drawdown': -0.00974568159280631, 'trades': 193}, 'T0.5': {'total_return': 0.46464605286728156, 'sharpe': 1.821815422842791, 'calmar': 2.077170567822788, 'max_drawdown': -0.01555586905816686, 'trades': 207}, 'T0.7': {'total_return': 0.6447876971468531, 'sharpe': 1.4981919019812144, 'calmar': 1.3897600824777019, 'max_drawdown': -0.030465258106733617, 'trades': 239}, 'T1.0': {'total_return': 1.0202161741278037, 'sharpe': 1.377487921169465, 'calmar': 1.2153990907368288, 'max_drawdown': -0.049655636228183586, 'trades': 251}}
- **best_params**: {'T': 0.45834538759536636, 'feature_window': 65, 'max_bars_hold': 60, 'vol_z_min': 0.7448917392631468}
- **best_fitness**: 0.7613241225815941
- **best_metrics**: {'total_return': 0.39155123810964665, 'cagr': 0.027917516514188723, 'volatility': 0.015562407031736364, 'sharpe': 1.7775596091151185, 'sortino': 0.08746216329114452, 'max_drawdown': -0.012866270495469068, 'calmar': 2.169821979416649, 'trades': 199, 'win_rate': 0.6733668341708543, 'profit_factor': 3.0554099721916037, 'avg_bars_held': 6.824120603015075, 'gross_profit': 58204.91161033733, 'gross_loss': 19049.787799372712}
- **walk_forward**: {'vetoed': False, 'veto_reasons': []}

## 失效原因 (Failure Reasons)

- fold1: decay=84%
- fold3: decay=64%

## 优化方向 (Optimization Direction)

- 若 OOS 衰减: 增加因子共振下限 / 缩小区间窗口 / 引入相对强度过滤
- 摩擦敏感性分析: 加密配置提高滑点假设检验鲁棒性

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*