# 估值 Skill — Valuation Engine V3（交易筛选估值）

## 目的
本任务不是给企业做投行级绝对估值，而是回答：**当前价格相对公司的核心盈利能力、三级同行和自身近180日市场定价，贵不贵；合理区间大概在哪；有没有足够安全边际。**

核心原则：**默认简单，异常升级。** 正常盈利公司禁止默认使用NAV/DCF等重模型。

## 1. Normal Valuation Path（默认路径）
适用于扣非/核心盈利为正、主营口径可比、没有重大重组/一次性污染、PE仍有经济意义的绝大多数公司。

固定顺序：
`核心盈利 → Forward核心EPS → 当前PE/TTM PE/动态PE → 同三级行业PE横比 → 盈利增速调整 → PB/ROE交叉验证 → 180日市场sanity → 合理PE区间 → 合理价格区 → 一次MOS → Safe Price Ceiling`

### 1.1 Forward核心EPS
优先使用扣非/核心盈利。半年报只有在季节性较稳定时才可合理年化；否则结合Q1/Q2边际、公司指引、订单/销量等构造Forward区间。股本发生重大变化时必须用当前/Forward稀释股本重算EPS。

### 1.2 PE主锚
必须获取并记录：
- 当前/TTM PE；
- 动态PE（可得时）；
- 同三级行业可比公司PE中位数与分位；
- 公司核心盈利增速。

合理PE不是固定行业表，而是从“三级同行中位数 + 公司自身动态PE + 盈利增长/质量”构造并解释。

基本原则：
- 盈利增速、ROE/现金质量明显优于同行，可允许合理溢价；
- 盈利增速低于同行或现金质量差，应折价；
- 当前PE只是参考，不能直接把当前估值复制成合理估值。

### 1.3 PB/ROE交叉验证
PB不是正常公司的主模型，但必须作为第二视角。比较公司PB与三级同行PB中位数，并结合ROE/资产质量解释溢价或折价。

典型异常：PE看起来很便宜，但PB很高且ROE不支持；或PE很贵，但PB/ROE与高质量资产明显支持。出现明显冲突时进入Exception Path，而不是机械平均。

### 1.4 180日市场sanity check
必须读取最近180个交易日：价格low/median/high、当前价格percentile，最好同时使用可得的历史估值分位。

用途是检查模型是否明显脱离市场现实：
- 如果模型合理价长期远低于过去180日主要交易区，而盈利又在改善且没有结构性恶化，优先怀疑模型；
- 如果基本面发生结构性变化，历史价格只能参考，不能强行把合理价拉回历史区间。

180日市场数据是sanity，不是“市场永远正确”。

### 1.5 合理价与安全价
先形成 `fair_pe_low/mid/high`，再用Forward核心EPS得到 `reasonable_price_range` 与 `base_fair_value`。

MOS只应用一次：
`safe_price_ceiling = base_fair_value × (1 - MOS)`

参考：高置信10%–15%，中等15%–20%，低置信20%–25%。不得再对合理价下沿重复打折。

## 2. Exception Path（仅异常公司）
只有以下情况才升级复杂模型：
- PE为负或没有经济意义；
- 重大重组/主营切换；
- 一次性收益显著污染；
- 银行/保险等资产负债表业务；
- 极端周期顶部/底部导致TTM PE失真；
- PE与PB/同行出现无法解释的重大冲突；
- 模型与180日市场定价严重冲突且简单复核不能解释；
- 商业模式发生断裂。

异常模型可使用 PB-ROE、Residual Income、EV/EBITDA、NAV/DCF、FCF/DCF 或 case-specific。必须记录 `exception_trigger`，没有触发不得升级复杂模型。

## 3. 极端偏离审计
若合理价与当前价偏离达到Manifest阈值，先做简单复核：
1. Forward核心EPS是否错；
2. 股本/重组/一次性收益是否错；
3. 三级同行PE/PB是否取错；
4. 盈利增速与现金质量调整是否合理；
5. 180日市场sanity是否出现强冲突。

只有上述仍无法解释，才升级复杂模型。禁止为了证明极端估值而直接堆NAV/DCF。

## 4. 必须输出
正常公司至少输出：
`current_price / price_date / current_pe / dynamic_pe / pb / core_profit_growth / peer_pe_median / peer_pb_median / fair_pe_low-mid-high / pe_basis / pb_cross_check / peer_valuation_check / market_180d_sanity_check / reasonable_price_range / base_fair_value / margin_of_safety_pct / safe_price_ceiling / valuation_position / falsifiers / valuation_path=normal_relative`。

异常公司必须额外输出：
`valuation_path=exception / exception_trigger / exception_method / exception_evidence`。

## 5. Completion纪律
- valuation_set逐只执行；
- 正常公司必须完成PE主锚、PB/ROE交叉验证、三级同行比较和180日sanity；
- 异常公司必须有明确异常触发，不得默认走复杂模型；
- Safe Price Ceiling只应用一次MOS；
- 估值完成不代表可买，最终仍与独立价格结构结合。
