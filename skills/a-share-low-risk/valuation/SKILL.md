# 估值 Skill

## 目的
回答每个`valuation_set`公司的：当前价格、合理价格、安全价格（低风险区）、估值位置。进入公司层后数量已经有限，因此默认要求**逐公司执行完整估值**，而不是只选择估值方法后停止。

## 固定顺序
`真实盈利 → 盈利类型 → Forward/正常化盈利 → 合理估值方法 → 模型执行 → 合理价格 → 敏感性/不确定性 → Margin of Safety → 安全价格 → 估值位置`

## 路线
- 成长/稳定：`Forward或正常化EPS × justified PE`，结合增长持续性、ROE/ROIC、利润率、现金转换、资本强度和预测可见度；历史/同行/PEG只作sanity check。
- 金融：`PB-ROE`为主，关注可持续ROE、资产质量和资本充足。
- 资源/强周期：`商品/价差/供需位置 → 正常化盈利或ROE → 周期中枢估值 → PB/资产价值交叉检查`，禁止把高景气利润直接乘PE。
- 订单型周期：用订单、交付、价格、成本和可持续利润率构造正常化盈利，再做周期中枢估值。

## 缺一致预期时必须自行构造区间
没有卖方一致预期、没有现成Forward EPS、没有现成“合理PE”都**不是停止估值的理由**。

必须继续使用公开证据构造审慎区间，例如：
- 已披露年度/季度/TTM扣非盈利；
- Q1/Q2或最近几个季度的边际趋势；
- 订单、销量、产品价格、产量、产能利用率；
- 毛利率/净利率、成本与费用率；
- 公司指引、产能投放、行业供需；
- 周期品的中枢价格/价差和正常化产量。

允许给**宽而诚实的估值区间**，不要求伪精确点估值。预测不确定性越大，合理区间越宽，安全边际越高。

## 完整估值桥
每家公司至少回答：
- `current_price`与`price_date`；
- `earnings_type`；
- `earnings_basis`：明确数值/区间及构造方法；
- `primary_method`；
- `key_assumptions`；
- `reasonable_price_assumption`；
- `reasonable_price_range`；
- `uncertainty`；
- `margin_of_safety_reason`；
- `safe_price_range`；
- `valuation_position`；
- `falsifiers`；
- `valuation_attempt_complete=true`；
- `model_execution_status`。

只写“应该用Forward PE”“需要正常化铜价”“需要建立2027E EPS”属于**方法选择**，不是估值执行完成。

## valuation_position
至少明确区分：`below_safe / in_safe_zone / fair / above_fair / materially_overvalued / review_required`。位置只能由当前价格与已经独立算出的合理/安全区间比较得出，不能让当前价格反向影响内在价值。

## review_required：严格异常出口
`review_required`不是普通结论，而是经过完整研究尝试后仍无法形成可靠区间的异常状态。

仅允许以下类型：
- `major_restructuring`：重大重组导致历史/未来盈利口径断裂；
- `nonrecurring_earnings_dominant`：一次性收益主导且无法可靠剥离；
- `critical_public_data_unavailable`：关键公开数据确实不可得；
- `model_instability`：在合理假设范围内估值结果极端不稳定；
- `business_model_break`：商业模式或主营发生重大断裂；
- `other_material_blocker`：其他实质性障碍，必须具体说明。

以下理由**不允许**直接review_required：
- 没有卖方一致预期；
- 没有现成Forward EPS；
- 需要正常化商品价格；
- 半年报不能简单年化；
- 不知道该用多少PE但尚未做增长/ROIC/历史周期研究。

使用review_required时仍必须记录：
`valuation_attempt_complete=true / model_execution_status=blocked_after_full_attempt / review_exception_code / attempted_inputs / blocker_evidence / review_reason`。

## Completion纪律
- `valuation_set`每家公司都必须执行；
- 非review公司必须给出`reasonable_price_range`、`safe_price_range`和`valuation_position`；
- 重点盈利链至少要有1家公司形成完整、非review的估值桥，才允许该链`opportunity_resolution_complete=true`；
- 如果某重点链所有公司都review_required，则估值Gate失败，应标记研究未完成，而不是用“无当前机会”绕过估值。

## 合理价格与安全价格
二者必须基于同一盈利基础。当前价格不能进入合理价格计算。历史价格不得决定或裁剪合理/安全价格。同行估值只作sanity check，不能与主模型机械平均。

## 持久化
估值只写本次`research_state.json`的`valuations`，不读取旧估值结果作为当前内在价值输入，也不写独立估值缓存。
