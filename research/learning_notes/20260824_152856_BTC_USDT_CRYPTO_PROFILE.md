# 学习笔记: BTC/USDT_CRYPTO_PROFILE

- **时间**: 2026-08-24T15:28:56
- **版本**: 0.1.0

## 决策路径 (Decision Path)
1. 知识提取: 主教材(284页,114k字符) + 课件OCR(15页) -> 因子矩阵 v0.1 (18个基础/事件/结构因子)
2. 温度参数 T∈[0.1,1.0] 线性插值: 共振数/止损/盈亏比/仓位
3. 贝叶斯优化 40 trials -> 最优参数 {'T': 0.9554584254395023, 'feature_window': 60, 'max_bars_hold': 120, 'vol_z_min': 0.3025234027108539}
4. Walk-Forward 4 折: 验证结果 REJECTED (decay>30%)

## 结果快照 (Results Snapshot)

- **grid**: {'T0.1': {'total_return': 0.0, 'sharpe': 0.0, 'calmar': 0.0, 'max_drawdown': 0.0, 'trades': 0}, 'T0.3': {'total_return': 0.008227640356371024, 'sharpe': 0.6385009055369941, 'calmar': 3.916269061370659, 'max_drawdown': -0.00041880144124084584, 'trades': 2}, 'T0.5': {'total_return': 0.03222012677563568, 'sharpe': 0.8515377022623557, 'calmar': 0.9784180376679792, 'max_drawdown': -0.006502889750852114, 'trades': 7}, 'T0.7': {'total_return': 0.12339784957866873, 'sharpe': 1.18066317657141, 'calmar': 1.4984526254711394, 'max_drawdown': -0.015712524328564514, 'trades': 14}, 'T1.0': {'total_return': 0.40823860465511874, 'sharpe': 1.816535165448144, 'calmar': 3.2649689634475942, 'max_drawdown': -0.021705043662292756, 'trades': 26}}
- **best_params**: {'T': 0.9554584254395023, 'feature_window': 60, 'max_bars_hold': 120, 'vol_z_min': 0.3025234027108539}
- **best_fitness**: 0.8484849934581742
- **best_metrics**: {'total_return': 0.39805489837993546, 'cagr': 0.06931299600165342, 'volatility': 0.036844511386429135, 'sharpe': 1.8383220653101087, 'sortino': 0.07606254002186245, 'max_drawdown': -0.020853339044766384, 'calmar': 3.323832018117457, 'trades': 26, 'win_rate': 0.8461538461538461, 'profit_factor': 7.734969378354541, 'avg_bars_held': 11.038461538461538, 'gross_profit': 45715.76018991581, 'gross_loss': 5910.270351922313}
- **walk_forward**: {'vetoed': True, 'veto_reasons': [{'fold': 2, 'reason': 'calmar_decay', 'decay': 1.0}, {'fold': 2, 'reason': 'sharpe_decay', 'decay': 1.0}]}

## 失效原因 (Failure Reasons)

- fold2: decay=100%

## 优化方向 (Optimization Direction)

- 若 OOS 衰减: 增加因子共振下限 / 缩小区间窗口 / 引入相对强度过滤
- 摩擦敏感性分析: 加密配置提高滑点假设检验鲁棒性

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*