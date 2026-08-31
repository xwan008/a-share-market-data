# 估值 Skill

## 目的
回答：当前价格、合理价格、安全价格（低风险区）。本Skill规定模型与估值纪律，不预设个股倍数答案。

## 固定顺序
`真实盈利 → 盈利类型 → Forward/正常化盈利 → 合理估值方法 → 合理价格 → 不确定性 → Margin of Safety → 安全价格 → 估值位置`

## 路线
- 成长/稳定：`Forward或正常化EPS × justified PE`，结合增长持续性、ROE/ROIC、利润率、现金转换、资本强度和预测可见度；历史/同行/PEG只作sanity check。
- 金融：`PB-ROE`为主，关注可持续ROE、资产质量和资本充足。
- 资源/强周期：`商品/价差/供需位置 → 正常化盈利或ROE → 周期中枢估值 → PB/资产价值交叉检查`，禁止把高景气利润直接乘PE。
- 无法可靠估值：输出`review_required`，不制造精确区间。

## 完整估值桥
可发布机会的`valuation_bridge`必须至少完整回答：
- `current_price`与`price_date`；
- `earnings_type`；
- `earnings_basis`：具体使用何种Forward/TTM/正常化盈利以及数值或区间；
- `primary_method`；
- `key_assumptions`；
- `reasonable_price_assumption`：倍数、PB/ROE、周期中枢或资产价值等关键估值假设；
- `reasonable_price_range`；
- `uncertainty`；
- `margin_of_safety_reason`；
- `safe_price_range`；
- `valuation_position`；
- `falsifiers`。

只写“应该用Forward PE”或“需要正常化铜价”属于**方法选择**，不属于完成估值桥。

## review_required 的处理
若关键盈利基础、周期中枢、资产负债表约束或模型敏感性无法可靠解决，可输出`review_required=true`。此时：
- 不得制造合理价格/安全价格；
- 该公司不能进入【当前机会】；
- 需要明确`review_reason`和缺失的关键变量；
- 若该链所有候选都只能review_required，可以把该链解析为“当前无可发布机会”，而不是让整个研究为了凑估值区间失真。

因此Completion Gate要求的是**机会解析完成**，而不是强迫每家公司都产生精确估值。任何真正进入【当前机会】的公司必须有完整估值桥。

## 合理价格与安全价格
二者必须基于同一盈利基础。当前价格不能进入合理价格计算。历史价格不得决定或裁剪合理/安全价格。同行估值只作可比性检查，不能与主模型机械平均。

## 最低输出
`current_price/price_date`、`earnings_type`、`earnings_basis`、`primary_method`、`key_assumptions`、`reasonable_price_assumption`、`reasonable_price_range`、`uncertainty`、`margin_of_safety_reason`、`safe_price_range`、`valuation_position`、`peer_sanity`、`history_reference`、`falsifiers`、`review_required`及原因。

## 持久化
估值只写本次`research_state.json`的`valuations`，统一使用当前字段，不读取或兼容旧研究状态字段作为当前估值输入。
