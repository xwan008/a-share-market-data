# 价格与预期差 Skill

## 目的
判断基本面改善已经被股价交易了多少，同时给出价值位置与价格状态。价值判断和结构判断独立计算，再汇总为预期差状态。

# A. 价值/预期差
## 四类主估值方法
1. 稳定成长/制造：Forward PE + 公司历史PE分位交叉检查。
2. 银行/保险/券商：PB + Forward ROE；PE只做辅助。
3. 标准商品周期：长期中性商品/价差 → 正常化EPS → 保守PE；短期商品走强不能直接抬买点。
4. 复杂周期制造：Forward PE + PB/历史估值至少两把独立尺子交叉验证。

## 核心规则
- 盈利驱动confidence不直接进入估值乘数。
- 同一周期风险禁止通过EPS haircut、regime haircut、低PE、统一买入折价多次惩罚。
- 安全区来自至少两个独立估值锚重叠，不来自统一 `fair_value × 0.8`。
- 当前价只在估值锚形成后用于判断位置。
- 多种方法明显冲突时输出 `valuation_divergence`，不得给正式买点。

# B. 全市场独立价格状态
## 扫描宇宙
价格结构先扫描全部具备新鲜180日历史的主板股票，绝不能读取`company_research`候选作为边界。风险警示证券仍要扫描以保证全集完整，但不得进入低风险机会候选。

## 结构类型
- `base_not_started`：价格仍在底部/平台，没有确认；
- `trend_continuation`：Price > MA20 > MA60、均线向上、高低点抬升、相对强度健康；
- `breakout`：突破60/120日平台或新高，并完成量价与收盘确认；
- `pullback`：既有强趋势内回踩MA20/MA60/突破位，且相对强度仍健康；
- `overheated`：趋势强但乖离/短期涨幅过大；
- `damaged`：关键支撑失效或中期结构转弱；
- 其余为`transition`。

## Breakout确认
突破资格必须同时满足：
1. 价格实际触及/突破60或120日关键高点，收盘保持在突破位附近之上；
2. 成交量确认：单日量相对前20日均量明显放大，或最近5日均量较前20日基准持续放大；
3. 收盘位置不能明显回落到当日区间下部。

机械基准可用：`volume_ratio_1d_vs_20d >= 1.15` 或 `volume_ratio_5d_vs_20d >= 1.05`，且 `close_location_pct >= 55`。贴近前高但没有量价确认只能 `watch_breakout`，不能标成正式breakout。该阈值是结构确认规则，不是个股特例。

## Pullback相对强度
回踩不是“跌得多”。除趋势/支撑结构成立外，20日相对市场强度不得显著转弱。机械基准：`relative_strength_20d_vs_market_pct >= -2%`。低于该阈值的形态只能观察，不得直接`participate`。

## 创新高与追高风险
- 上方无历史压力不是缺陷，可以是价格发现；
- 第一压力不足10%不能一刀切淘汰突破型机会；
- 趋势强和买点好是两个判断，必须独立输出`chase_risk`；
- `chase_risk=high`时即使趋势强，也应等回踩而不是把趋势判弱。

追高风险至少考虑：price/MA20、price/MA60乖离，最近10/20日涨幅，ATR/波动扩张，量价确认。

# C. 预期差状态
- `large_gap_not_started`：盈利明显改善、估值/涨幅未透支、价格未启动；
- `gap_just_starting`：盈利改善且刚突破/刚转强，优先级最高；
- `trend_confirmed_gap_remaining`：趋势确认但仍有基本面/估值空间；
- `priced_in_or_overheated`：盈利好但股价已充分交易或过热；
- `fundamental_price_conflict`：基本面与市场结构相互矛盾，需要等待。

## 输出
- `data/research/v2/full_market_price_structure.json`
- `data/research/v2/price_expectation_gap.json`
