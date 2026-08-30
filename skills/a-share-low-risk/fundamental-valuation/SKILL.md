# 非周期公司左侧估值 Skill

## 目的
把非周期公司的左侧价值判断从“当前PE看起来便宜/贵”改成可追溯的前瞻盈利与合理估值计算。适用于盈利不主要由单一商品/价差主导的公司；周期/资源公司必须转交 `cycle-valuation` Skill。

## 输入
- 已通过 `earnings-validation` 的共同资格池公司。
- 最新财报、管理层指引、订单/出货/客户/产品结构、竞争格局、行业增速等前瞻证据。
- 当前价格只用于最后比较价格位置，禁止反向决定价值锚。

## 固定算法
1. 判断估值模型：`forward_pe / ev_ebitda / pb_roe / sum_of_parts / other`，并解释为什么适用。
2. 构建未来12个月或未来4季度的正常化盈利中枢：优先从未来1–2季度盈利链向后滚动，不得简单把最新半年利润乘2。
3. 给出 `bear/base/bull` 盈利假设或至少合理上下界；明确收入增速、利润率、份额/产品结构等关键敏感度。
4. 确定合理估值区间。估值必须由增长持续性、ROE/现金流、竞争格局、业务质量、历史/可比区间等共同支撑；不能因为股价已经上涨而提高合理倍数。
5. 计算 `value_anchor = forward_earnings × reasonable_multiple`（或对应模型）；必须展示计算桥梁。
6. 再用当前价计算安全边际和价格位置，形成 `safe_buy_range / reasonable_buy_range / expensive_or_wait`。
7. 若关键盈利输入、估值方法或一次性因素无法可靠拆分，输出 `valuation_status=unavailable`，不能猜精确区间。

## 输出
每只公司至少包含：
- `code/name/current_price`
- `valuation_model`
- `forward_earnings_basis`
- `bear/base/bull_forward_earnings` 或等价区间
- `reasonable_multiple_range` 与依据
- `value_anchor_range`
- `safe_buy_range`
- `reasonable_buy_range`
- `margin_of_safety`
- `key_sensitivities`
- `valuation_status = valid/unavailable`
- `invalidation_condition`

## 硬规则
- TTM PE/PB只能作为交叉检查，不是价值锚生成器。
- 当前价、技术突破、HH/HL、市场热度不能进入合理估值倍数的因果输入。
- 所有正式价值锚必须能从输出字段重新计算得到。
- 若公司实际属于商品/价差高敏感模型，必须改走 `cycle-valuation`，不得用本 Skill 绕过商品锚。
