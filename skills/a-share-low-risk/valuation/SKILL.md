# 估值 Skill — 交易筛选估值

## 目的
本任务不是给企业做投行级绝对估值，而是回答四件事：**核心盈利是否可持续、企业大致值多少钱、当前价格是否具备安全边际、真正适合低风险左侧参与的合理买入区在哪里。**

核心原则：**默认简单，异常升级；估值决定 WHERE，不决定 WHEN。价格结构不得反向修改估值。**

## 1. Normal Valuation Path
适用于扣非/核心盈利为正、主营口径可比、没有重大重组/一次性污染、PE仍有经济意义的绝大多数公司。

固定顺序：
`核心盈利 → Forward核心EPS → 当前/TTM PE + 动态PE → 同三级行业PE横比 → 核心盈利增速调整 → PB/ROE交叉验证 → 周期/口径检查 → 180日市场sanity → fair PE区间 → reasonable_price_range → base_fair_value → 一次MOS → safe_price_ceiling → reasonable_buy_range`

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

### 1.4 周期与口径检查
在形成Forward盈利桥之前必须检查：
- 是否处于商品价格、价差、运价、库存周期等明显高景气阶段；
- 当前高增速是否来自低基数、产能一次性释放、重大资产注入或主营切换；
- TTM/半年报盈利是否可能明显高于可持续的中枢盈利。

对强周期公司，禁止把景气高点的TTM盈利或极高同比增速机械外推到长期合理价。应优先使用正常化/中周期核心盈利、可验证的Forward产销量与成本假设；若周期扭曲严重，则触发 `extreme_cycle_distortion` 进入Exception Path。

### 1.5 180日市场 sanity check
必须读取最近180个交易日：价格 low/median/high、当前价格 percentile；历史估值分位可得时一并使用。

其作用只检查模型是否明显脱离现实，不能反向用市场价格“拟合”内在价值。若基本面发生结构性变化，历史价格只能参考。

### 1.6 合理价值、安全价与合理买入区
三者必须严格区分：

1. `reasonable_price_range`：由Forward核心EPS × fair PE区间得到的**合理价值区间**，回答“大致值多少钱”；
2. `safe_price_ceiling`：在 `base_fair_value` 上只应用一次MOS得到的**安全价格上限**，回答“最高到什么价格仍有足够安全边际”；
3. `reasonable_buy_range`：本榜单真正使用的**低风险合理买入区间**，回答“在哪里可以做左侧参与”。

`safe_price_ceiling` **不是** `reasonable_buy_range`，不得把“低于安全价上限”全部视为买点。

`reasonable_buy_range` 必须：
- 完全由估值层产生，不参考技术结构；
- 是有上下界的区间，而不是单一最高价；
- 上沿不得高于 `safe_price_ceiling`；
- 结合保守Forward核心盈利、fair PE/PB交叉验证、周期正常化与一次MOS形成；
- 若区间明显宽到失去交易意义，必须缩窄假设或进入review，不能直接发布宽泛区间；
- 不得再次对已经应用MOS的结果重复打折。

MOS只应用一次：
`safe_price_ceiling = base_fair_value × (1 - margin_of_safety_pct)`

参考：高置信10%–15%，中等15%–20%，低置信20%–25%。不得用“低EPS + 低PE + 再对合理价下沿打折”制造重复保守。

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
若模型合理价、合理买入区与当前价出现严重偏离，先复核：
1. Forward核心EPS是否错误外推高增长；
2. 股本/重组/一次性收益；
3. 三级同行PE/PB；
4. 盈利增速、ROE与现金质量调整；
5. 周期位置与正常化盈利；
6. 180日市场sanity。

只有简单复核仍无法解释时才升级复杂模型。禁止为了证明极端估值直接堆NAV/DCF。

## 4. 必须输出
正常公司至少输出：
`current_price / price_date / current_pe / dynamic_pe / pb / roe / core_profit_growth / peer_pe_median / peer_pb_median / fair_pe_low / fair_pe_mid / fair_pe_high / pe_basis / pb_cross_check / peer_valuation_check / cycle_normalization_check / market_180d_sanity_check / reasonable_price_range / base_fair_value / margin_of_safety_pct / safe_price_ceiling / reasonable_buy_range / valuation_position / falsifiers / valuation_path=normal_relative`。

异常公司额外输出：
`valuation_path=exception / exception_trigger / exception_method / exception_evidence / reasonable_buy_range`。

## 5. Completion纪律
- valuation_set逐只执行；
- 正常公司必须完成PE主锚、PB/ROE交叉验证、周期/口径检查、三级同行比较和180日sanity；
- 异常公司必须有明确异常触发；
- Safe Price Ceiling只应用一次MOS；
- 每个非review公司必须产生可解释的 `reasonable_buy_range`；
- 估值完成后，**当前价格进入 `reasonable_buy_range` 即具备左侧价值买点资格**；
- 价格结构只用于进一步判断是否进入“左侧拐点买点榜”，不得否决已经成立的左侧价值买点资格。
