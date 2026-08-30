# 最终机会排序 Skill

## 目的
把公司盈利研究、估值锚、正式买入区间、预期差和价格状态整合成可执行机会榜。Shadow可以保留趋势研究对象；Production“新买点”必须真正处于低风险买入区。

## 每只候选固定输出
- 股票、代码、当前价；
- 主盈利Driver与未来1–2季度Forward Bridge；
- 财报级扣非/现金流证据；
- `fundamental_anchor_range`；
- `value_anchor_range`；
- `safe_buy_range`；
- `reasonable_buy_range`；
- 当前价值位置；
- `independent_v2_anchor_count`与锚冲突状态；
- 隐含PE/PB；
- 价格结构、追高风险、动作与失效条件。

## 排序维度
盈利质量、Forward Visibility、价值位置、Expectation Gap、Price Timing、Valuation Sanity。分数只能排序，不能修复硬门槛。

## 机会状态
- `LEFT_WATCH`：价值成立但价格尚未确认，或处买入区但技术尚未启动。
- `WAIT_BREAKOUT`：处可接受价值位置，等待量价突破。
- `PRIORITY_INFLECTION`：盈利改善 + 正式买入区 + 当前价仍可买 + 股价刚启势。
- `RIGHT_PARTICIPATE`：趋势确认且仍有价值空间；Shadow可以保留此状态。
- `WAIT_PULLBACK`：趋势强但过热或已离开合理买入区。
- `REJECT`：盈利逻辑失效、结构破坏、风险警示、严重估值冲突等。

## Production新买点硬门槛
必须同时满足：
1. 财报级盈利证据ready：扣非盈利、一次性因素、现金流、Forward Bridge通过；
2. `formal_buy_zone_ready = true`；
3. 当前`value_gap_state`只能是`safe_buy_zone`或`reasonable_buy_zone`；
4. 价格结构不能damaged/overheated，追高风险不能high；
5. 其它Manifest Production Gate全部通过。

**当前价高于合理区上沿时，即使公司好、趋势强、距离公允价值仍有空间，也不能作为“低风险新买点”。** 可继续作为Shadow趋势/持有观察，等待回踩合理区。

当前价显著低于安全区下沿时也不能自动发布正式买点，先进入`deep_discount_review`排查价值陷阱。

## Top3
Shadow Top3优先展示“当前真的在安全/合理区”的高质量候选，再展示其它研究机会。Production Top3只从完整硬门槛通过者产生。允许少于3只或为空，禁止凑数。

## 产业链集中度
同一Driver主榜原则上不超过2家。

## 输出
V2 Shadow写入`data/research/v2/opportunity_ranking.json`。在连续Shadow验证完成前不覆盖V1正式榜单。Validator必须case-free。
