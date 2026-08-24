# 学习笔记: AAPL_US_EQUITY_PROFILE

- **时间**: 2026-08-24T15:18:18
- **版本**: 0.1.0

## 决策路径 (Decision Path)
1. 知识提取: 主教材(284页,114k字符) + 课件OCR(15页) -> 因子矩阵 v0.1 (18个基础/事件/结构因子)
2. 温度参数 T∈[0.1,1.0] 线性插值: 共振数/止损/盈亏比/仓位
3. 贝叶斯优化 40 trials -> 最优参数 {'T': 0.922980095435161, 'feature_window': 70, 'max_bars_hold': 110, 'vol_z_min': 1.0356675390068357}
4. Walk-Forward 4 折: 验证结果 REJECTED (decay>30%)

## 结果快照 (Results Snapshot)

- **grid**: {'T0.1': {'total_return': 0.003115808678860965, 'sharpe': 0.23686176800711375, 'calmar': 0.21757389375112843, 'max_drawdown': -0.002393188449379302, 'trades': 9}, 'T0.3': {'total_return': 0.026514506297878437, 'sharpe': 0.8625514040801043, 'calmar': 1.1927049777278869, 'max_drawdown': -0.003679445339123344, 'trades': 19}, 'T0.5': {'total_return': 0.14241285859759878, 'sharpe': 1.908672309215122, 'calmar': 3.1495610901444007, 'max_drawdown': -0.007153016586144645, 'trades': 27}, 'T0.7': {'total_return': 0.23508065056406013, 'sharpe': 1.7215119484336416, 'calmar': 2.1631244940654724, 'max_drawdown': -0.01662460017039591, 'trades': 40}, 'T1.0': {'total_return': 0.4736095821444759, 'sharpe': 1.7812989167423992, 'calmar': 1.9506488147235514, 'max_drawdown': -0.03436156176420535, 'trades': 52}}
- **best_params**: {'T': 0.922980095435161, 'feature_window': 70, 'max_bars_hold': 110, 'vol_z_min': 1.0356675390068357}
- **best_fitness**: 0.8677971489523735
- **best_metrics**: {'total_return': 0.4665688329241786, 'cagr': 0.0661725621490763, 'volatility': 0.03320901084418818, 'sharpe': 1.947504302103312, 'sortino': 0.10322843193724789, 'max_drawdown': -0.01845107135566093, 'calmar': 3.5863804802193258, 'trades': 49, 'win_rate': 0.7142857142857143, 'profit_factor': 3.991554342697043, 'avg_bars_held': 7.530612244897959, 'gross_profit': 62253.08444661598, 'gross_loss': 15596.201154198081}
- **walk_forward**: {'vetoed': True, 'veto_reasons': [{'fold': 1, 'reason': 'calmar_decay', 'decay': 1.360186605642723}, {'fold': 1, 'reason': 'sharpe_decay', 'decay': 1.4571400203317202}]}

## 失效原因 (Failure Reasons)

- fold1: decay=136%

## 优化方向 (Optimization Direction)

- 若 OOS 衰减: 增加因子共振下限 / 缩小区间窗口 / 引入相对强度过滤
- 摩擦敏感性分析: 加密配置提高滑点假设检验鲁棒性

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*