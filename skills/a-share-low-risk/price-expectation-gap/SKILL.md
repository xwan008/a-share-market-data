# 价格与预期差 Skill

## 目的
判断“基本面改善已经被股价交易了多少”，同时给出价值位置与价格结构。价值判断和结构判断使用不同数据、独立计算，但在同一Skill中汇总为预期差状态。

# A. 价值/预期差
## 估值只保留四类主方法
1. 稳定成长/制造：Forward PE + 公司历史PE分位交叉检查。
2. 银行/保险/券商：PB + Forward ROE；PE只做辅助。
3. 标准商品周期：长期中性商品/价差 → 正常化EPS → 保守PE；短期商品走强不能直接抬买点。
4. 复杂周期制造：Forward PE + PB/历史估值至少两把独立尺子交叉验证。

## 核心规则
- 产业/盈利驱动的confidence不直接进入估值乘数。
- 禁止重复折价：同一周期风险不能同时通过EPS haircut、regime haircut、低PE和统一买入折价多次惩罚。
- 安全区来自至少两个独立估值锚的重叠或明显共同低估，不来自统一 `fair_value × 0.8`。
- 合理区是保守公允价值附近的可解释范围，允许整数/一位小数，不制造虚假精度。
- 当前价只在估值锚形成后用于判断位置。

## 估值Sanity
正式区间必须反推隐含PE/PB并检查：
- 是否显著低于公司/行业长期历史底部；
- 是否显著高于历史高位；
- 若异常，是否存在盈利崩塌、资产减值、极端周期等明确证据。

多种方法明显冲突时输出 `valuation_divergence`，不得给正式买点。

# B. 全市场独立价格状态
## 候选宇宙
RIGHT/价格结构扫描必须覆盖所有具备新鲜180日历史的主板股票，绝不能读取`company_research`候选作为扫描边界。

## 结构类型
至少识别：
- `base_not_started`：基本面候选但价格仍在底部/平台，没有确认；
- `trend_continuation`：Price > MA20 > MA60、均线向上、高低点抬升、相对强度健康；
- `breakout`：突破60/120日平台或新高并站稳；
- `pullback`：强趋势回踩MA20/突破位/前高支撑，量价健康；
- `overheated`：趋势强但乖离/短期涨幅过大，买点风险高；
- `damaged`：关键支撑失效或中期结构转弱。

## 创新高规则
- 上方无历史压力不是缺陷，可以是强趋势特征。
- `first_effective_resistance`只适用于仍在压力下方的结构。
- 突破型看“是否站稳突破”和失效位；创新高型看趋势质量与乖离风险。
- 禁止用“距第一压力<10%”一刀切淘汰突破型机会。

## 追高风险
至少输出：
- price/MA20、price/MA60乖离；
- 最近10/20日涨幅；
- ATR或等价波动扩张；
- volume/price confirmation；
- `chase_risk` = low / medium / high。

趋势强但`chase_risk=high`时动作应是“等回踩”，而不是把趋势判断改成弱。

# C. 预期差状态
对公司研究候选结合价值与结构形成：
- `large_gap_not_started`：盈利明显改善、估值/涨幅未透支、价格未启动；
- `gap_just_starting`：盈利改善且刚突破/刚转强，优先级最高；
- `trend_confirmed_gap_remaining`：趋势确认但仍有基本面/估值空间；
- `priced_in_or_overheated`：盈利好但股价已充分交易或过热；
- `fundamental_price_conflict`：基本面与市场结构相互矛盾，需要等待。

## 输出
- 全市场价格结构：`data/research/v2/full_market_price_structure.json`
- 公司候选预期差：`data/research/v2/price_expectation_gap.json`
