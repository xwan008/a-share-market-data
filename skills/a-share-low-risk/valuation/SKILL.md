# 估值 Skill — 交易筛选估值

## 目的
本任务不是给企业做投行级绝对估值，而是回答：**当前价格相对公司的核心盈利能力、三级同行和自身近180日市场定价，贵不贵；合理区间大概在哪；有没有足够安全边际。**

核心原则：**默认简单，异常升级；估值只回答值多少钱，不回答什么时候买。**

## 1. Normal Valuation Path
适用于扣非/核心盈利为正、主营口径可比、没有重大重组/一次性污染、PE仍有经济意义的绝大多数公司。

固定顺序：
`核心盈利 → Forward核心EPS → 当前/TTM PE + 动态PE → 同三级行业PE横比 → 核心盈利增速调整 → PB/ROE交叉验证 → 180日市场sanity → fair PE区间 → reasonable price → base fair value → 一次MOS → safe_price_ceiling`

### 1.1 Forward核心EPS
优先使用扣非/核心盈利。半年报只有在季节性较稳定时才可合理年化；否则结合季度边际、公司指引、订单/销量等构造Forward区间。股本发生重大变化时必须用当前/Forward稀释股本重算EPS，禁止跨重大股本变化直接缩放历史EPS。

### 1.2 PE主锚
必须获取并记录：
- 当前/TTM PE；
- 动态PE（可得时）；
- 同三级行业经济机制可比公司的PE中位数/分位；
- 公司核心盈利增速。

合理PE不是固定一级行业表，而是从“三级同行中位数 + 公司自身动态PE + 盈利增长/质量”构造并解释。当前PE只是参考，不能直接复制成合理估值。

### 1.3 PB/ROE交叉验证
必须用PB/ROE作为第二视角。若行情接口缺PB，但最新财报存在净资产，先按统一口径自算PB，而不是直接进入review。

比较公司PB与三级同行PB中位数，并结合ROE、资产质量和现金质量解释溢价/折价。若PE/PB/同行出现无法解释的重大冲突，进入Exception Path，而不是机械平均。

### 1.4 180日市场 sanity check
必须读取最近180个交易日：价格 low/median/high、当前价格 percentile；历史估值分位可得时一并使用。

其作用只检查模型是否明显脱离现实，不能反向用市场价格“拟合”内在价值。若基本面发生结构性变化，历史价格只能参考。

### 1.5 合理价与安全价
先形成 `fair_pe_low / fair_pe_mid / fair_pe_high`，再由Forward核心EPS得到 `reasonable_price_range` 与 `base_fair_value`。

MOS只应用一次：
`safe_price_ceiling = base_fair_value × (1 - margin_of_safety_pct)`

参考：高置信10%–15%，中等15%–20%，低置信20%–25%。不得用“低EPS + 低PE + 对合理价下沿再打折”制造重复保守。

## 2. Exception Path
只有Manifest明确的异常触发存在时才升级复杂模型，例如：
- PE为负/失去经济意义；
- 重大重组或主营切换；
- 一次性收益显著污染；
- 银行/保险等资产负债表业务；
- 极端周期导致TTM PE失真；
- PE与PB/同行出现无法解释的重大冲突；
- 模型与180日市场定价严重冲突且简单复核不能解释；
- 商业模式发生断裂。

可使用 PB-ROE、Residual Income、EV/EBITDA、NAV/DCF、FCF/DCF 或 case-specific。必须记录 `exception_trigger`，没有触发不得升级复杂模型。

## 3. 极端偏离审计
若模型合理价与当前价严重偏离，先复核：
1. Forward核心EPS；
2. 股本/重组/一次性收益；
3. 三级同行PE/PB；
4. 盈利增速、ROE与现金质量调整；
5. 180日市场sanity。

只有简单复核仍无法解释时才升级复杂模型。禁止为了证明极端估值直接堆NAV/DCF。

## 4. 必须输出
正常公司至少输出：
`current_price / price_date / current_pe / dynamic_pe / pb / roe / core_profit_growth / peer_pe_median / peer_pb_median / fair_pe_low / fair_pe_mid / fair_pe_high / pe_basis / pb_cross_check / peer_valuation_check / market_180d_sanity_check / reasonable_price_range / base_fair_value / margin_of_safety_pct / safe_price_ceiling / valuation_position / falsifiers / valuation_path=normal_relative`。

异常公司额外输出：
`valuation_path=exception / exception_trigger / exception_method / exception_evidence`。

## 5. Completion纪律
- valuation_set逐只执行；
- 正常公司必须完成PE主锚、PB/ROE交叉验证、三级同行比较和180日sanity；
- 异常公司必须有明确异常触发；
- Safe Price Ceiling只应用一次MOS；
- 估值完成不代表可买，最终仍必须与独立价格结构求交集。
