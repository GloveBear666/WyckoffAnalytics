# 学习笔记: BTC/USDT_CRYPTO_PROFILE

- **时间**: 2026-08-24T15:16:02
- **版本**: 0.1.0

## 决策路径 (Decision Path)
1. 知识提取: 主教材(284页,114k字符) + 课件OCR(15页) -> 因子矩阵 v0.1 (18个基础/事件/结构因子)
2. 温度参数 T∈[0.1,1.0] 线性插值: 共振数/止损/盈亏比/仓位
3. 贝叶斯优化 40 trials -> 最优参数 {'T': 0.4571735476273898, 'feature_window': 90, 'max_bars_hold': 90, 'vol_z_min': 1.5389328710242323}
4. Walk-Forward 4 折: 验证结果 REJECTED (decay>30%)

## 结果快照 (Results Snapshot)

- **grid**: {'T0.1': {'total_return': -0.025006089312351265, 'sharpe': -0.27635981312318847, 'calmar': -0.020023534454921776, 'max_drawdown': -0.02634126856620378, 'trades': 460}, 'T0.3': {'total_return': 0.0640991335618677, 'sharpe': 0.24347534396923454, 'calmar': 0.04424919889685861, 'max_drawdown': -0.029270201502328508, 'trades': 807}, 'T0.5': {'total_return': 0.18966247267420266, 'sharpe': 0.3961933847263927, 'calmar': 0.06292263061098285, 'max_drawdown': -0.05760519790846419, 'trades': 891}, 'T0.7': {'total_return': 0.22854905533002312, 'sharpe': 0.3087467449068564, 'calmar': 0.03674229828803414, 'max_drawdown': -0.11696090816400051, 'trades': 1038}, 'T1.0': {'total_return': 0.1632582476489326, 'sharpe': 0.1569707724746282, 'calmar': 0.01379383835560324, 'max_drawdown': -0.228760610965985, 'trades': 1122}}
- **best_params**: {'T': 0.4571735476273898, 'feature_window': 90, 'max_bars_hold': 90, 'vol_z_min': 1.5389328710242323}
- **best_fitness**: 0.11298624325513085
- **best_metrics**: {'total_return': 0.18269033238299914, 'cagr': 0.0035017791620273186, 'volatility': 0.00815668268630673, 'sharpe': 0.4326666351662275, 'sortino': 0.020696126162526748, 'max_drawdown': -0.03779182462776964, 'calmar': 0.09265970078232719, 'trades': 853, 'win_rate': 0.5416178194607268, 'profit_factor': 1.258259269448707, 'avg_bars_held': 8.313012895662368, 'gross_profit': 89008.15240834102, 'gross_loss': 70739.11917004117}
- **walk_forward**: {'vetoed': True, 'veto_reasons': [{'fold': 1, 'reason': 'calmar_decay', 'decay': 1.1151848145597887}, {'fold': 1, 'reason': 'sharpe_decay', 'decay': 1.2196650396032194}]}

## 失效原因 (Failure Reasons)

- fold1: decay=112%

## 优化方向 (Optimization Direction)

- 若 OOS 衰减: 增加因子共振下限 / 缩小区间窗口 / 引入相对强度过滤
- 摩擦敏感性分析: 加密配置提高滑点假设检验鲁棒性

---
*由 KNOWLEDGE_MANAGEMENT_LAYER 自动生成*