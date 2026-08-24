# 学习笔记: SPY_US_EQUITY_PROFILE

- **时间**: 2026-08-24T15:17:19
- **版本**: 0.1.0

## 决策路径 (Decision Path)
1. 知识提取: 主教材(284页,114k字符) + 课件OCR(15页) -> 因子矩阵 v0.1 (18个基础/事件/结构因子)
2. 温度参数 T∈[0.1,1.0] 线性插值: 共振数/止损/盈亏比/仓位
3. 贝叶斯优化 40 trials -> 最优参数 {'T': 0.189810768175771, 'feature_window': 75, 'max_bars_hold': 70, 'vol_z_min': 1.8708691406556965}
4. Walk-Forward 4 折: 验证结果 PASSED

## 结果快照 (Results Snapshot)

- **grid**: {'T0.1': {'total_return': 0.011273078592849206, 'sharpe': 1.1542843267146348, 'calmar': 1.1026309888303167, 'max_drawdown': -0.0017027810044467628, 'trades': 22}, 'T0.3': {'total_return': 0.05142796403202787, 'sharpe': 1.431269454670241, 'calmar': 1.4869061548703573, 'max_drawdown': -0.005667343504032307, 'trades': 47}, 'T0.5': {'total_return': 0.06937341163975819, 'sharpe': 1.1166486402200066, 'calmar': 0.8981863293142943, 'max_drawdown': -0.01256595453634346, 'trades': 49}, 'T0.7': {'total_return': 0.08460026662956888, 'sharpe': 0.7742053735534374, 'calmar': 0.6147518990411913, 'max_drawdown': -0.022256015871050194, 'trades': 64}, 'T1.0': {'total_return': 0.12150956871998875, 'sharpe': 0.7234820293027971, 'calmar': 0.40400667392995593, 'max_drawdown': -0.04795473810732043, 'trades': 70}}
- **best_params**: {'T': 0.189810768175771, 'feature_window': 75, 'max_bars_hold': 70, 'vol_z_min': 1.8708691406556965}
- **best_fitness**: 0.7783500321041994
- **best_metrics**: {'total_return': 0.04237820310562945, 'cagr': 0.006969205035848747, 'volatility': 0.0037921116540022572, 'sharpe': 1.834578063569877, 'sortino': 0.062079169124972564, 'max_drawdown': -0.0028244432552891885, 'calmar': 2.46746151575107, 'trades': 44, 'win_rate': 0.7045454545454546, 'profit_factor': 5.843788601034943, 'avg_bars_held': 2.159090909090909, 'gross_profit': 5112.718176596488, 'gross_loss': 874.8978660335213}
- **walk_forward**: {'vetoed': False, 'veto_reasons': []}

## 失效原因 (Failure Reasons)

- fold3: decay=72%

## 优化方向 (Optimization Direction)

- 若 OOS 衰减: 增加因子共振下限 / 缩小区间窗口 / 引入相对强度过滤
- 摩擦敏感性分析: 加密配置提高滑点假设检验鲁棒性

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*