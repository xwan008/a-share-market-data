# 估值 Skill

## 目的
回答两个问题：
1. 公司的正常盈利能力大致值多少钱；
2. 在估值不确定性下，什么价格区间才具有足够安全边际。

本Skill只规定模型选择与估值纪律，不预设个股PE/PB答案，也不使用同行或历史价格投票决定内在价值。

## 固定顺序
`真实盈利 → 盈利类型 → Forward/正常化盈利 → 合理估值方法 → Fair Value → 不确定性 → Margin of Safety → 低风险买入区`

## 估值路线
### 1. 成长/稳定经营公司
主方法：`Forward或正常化EPS × justified PE`。

合理PE需要解释来源，重点考虑未来盈利增长持续性、ROE/ROIC与增量回报、利润率稳定性、现金转换、资本强度/负债/稀释风险，以及盈利预测分歧和可见度。

PEG、历史PE、同行PE可以做sanity check，但不能作为机械定价公式，也不得用固定PEG阈值伪装成普遍规律。

### 2. 金融公司
主方法：`PB-ROE`。重点判断可持续ROE、资产质量、资本充足和增长/风险。PE只作辅助。

### 3. 资源/强周期公司
禁止直接把当前高景气利润乘PE。

固定顺序：
`商品/价差/供需位置 → 正常化盈利或ROE → 周期中枢下的估值 → PB/资产价值交叉检查`

必须区分当前利润中的周期windfall、可持续产量/成本优势、商品价格或价差的中期中枢、资产负债表和资源禀赋。低PE可能是周期顶部，高PE可能是周期底部。

### 4. 无法可靠估值
如果盈利基础不稳定、业务变化过快、关键数据缺失或模型对假设极端敏感，直接输出`review_required`，不要制造精确区间。

## Fair Value与低风险买入区
Fair Value是对正常盈利能力的合理价值估计；低风险买入区是在**同一盈利基础**上，为预测和模型误差保留安全边际后的行动区间。

正式展示时必须输出`fair_value_bridge`，至少包含：
- `earnings_basis`：使用什么Forward/正常化盈利；
- `fair_assumption`：Fair Value使用的方法、倍数或关键假设；
- `fair_value_range`；
- `uncertainty`：为什么可能估错；
- `entry_assumption`或`margin_of_safety_reason`：为什么要比Fair Value更保守；
- `buy_zone`。

如果不能解释“为什么Fair Value与买入区相差这些”，就不应输出精确买入区。

安全边际随不确定性变化：盈利越稳定、预测越可靠，所需折价通常越小；周期性越强、模型越敏感、预测分歧越大，所需安全边际通常越大。Skill不规定统一固定折价比例。

## 同行与历史的角色
同行估值只回答主估值是否明显脱离经济可比公司的常见定价；经济可比性优先于行业标签。同行结果只能提高/降低置信度或触发复核，不能与主模型简单平均投票。

历史估值与历史价格只回答市场过去如何定价、当前位于什么历史位置。历史价格不得决定Fair Value、作为独立估值锚投票，或裁剪/抬高基本面买入区。

## 每家公司最低输出
- `earnings_type`；
- `earnings_basis`；
- `primary_method`；
- `key_assumptions`；
- `fair_value_bridge`；
- `peer_sanity`；
- `history_reference`；
- `falsifiers`；
- `review_required`及原因（如适用）。

## Validator可以检查什么
- 模型是否与盈利类型匹配；
- 周期股是否使用了正常化盈利；
- EPS/PE/PB计算是否自洽；
- 当前价是否偷偷进入Fair Value计算；
- 历史价格是否被用于裁剪内在价值；
- 是否存在无法解释的重复折价；
- Fair Value与低风险区是否能从同一盈利基础解释。

Validator不能决定某家公司应该给多少PE，也不能用固定股票作为正确答案。

## 持久化
估值研究统一写入`data/research/v2/research_state.json`中的`valuations`部分。
