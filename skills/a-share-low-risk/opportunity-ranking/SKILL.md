# 最终机会排序 Skill

## 目的
把公司盈利研究、估值锚、正式买入区间、预期差和价格状态整合成可执行机会榜。最终排序不机械要求旧LEFT∩RIGHT，而是明确区分左侧关注、等待突破、刚启势、趋势参与、过热等待和拒绝。

## 输入
- `data/research/v2/company_research.json`
- `data/research/v2/valuation_anchors.json`
- `data/research/v2/price_expectation_gap.json`
- `data/research/v2/full_market_price_structure.json`
- 数据健康与双Validator状态

## 每只候选必须固定输出
- 股票、代码、当前价；
- 为什么进入研究池；
- 主盈利Driver与未来1–2季度Forward Bridge；
- `fundamental_anchor_range`：公司自身第一基本面公允价值锚；
- `value_anchor_range`：完成同行/历史成本交叉后的低风险价值观察区；
- `safe_buy_range`：安全买入区；
- `reasonable_buy_range`：合理买入区；
- 当前价属于安全区/合理区/区间上方/已充分定价/估值待复核；
- `independent_v2_anchor_count`与锚冲突状态；
- PE/PB隐含倍数sanity；
- 价格结构、追高风险与当前最合理动作；
- 失效条件。

缺失正式买点时不能留空不解释，必须输出具体blocker，例如：`fundamental_valuation_anchor_required / valuation_divergence / formal_buy_zone_required / deducted_profit_verification_required`。

## 排序维度
1. 盈利质量：主营/扣非、现金流、一次性收益风险。
2. Forward Visibility：未来1–2季度Bridge可验证性。
3. 价值位置：当前价相对安全区、合理区、公允锚的位置。
4. Expectation Gap：盈利改善相对股价定价还剩多少。
5. Price Timing：未启动/初启/趋势确认/回踩/过热/破坏。
6. Valuation Sanity：估值锚数量、同行分歧、隐含PE/PB。

分数只允许排序，不允许修复缺证据、缺估值锚或结构破坏。

## 机会状态
- `LEFT_WATCH`：基本面/估值成立，但价格尚未确认，或处安全/合理区但技术结构尚未启动。
- `WAIT_BREAKOUT`：基本面成立且价格临近有效平台，等待量价确认。
- `PRIORITY_INFLECTION`：盈利改善 + 正式估值区成立 + 仍有预期差 + 股价刚启势；最高优先级。
- `RIGHT_PARTICIPATE`：趋势确认，且合理价值空间仍未完全兑现。
- `WAIT_PULLBACK`：趋势强但过热/乖离过大，等待回到合理风险收益位置。
- `REJECT`：盈利逻辑失效、结构破坏、预期已充分交易、风险警示或严重估值冲突。

## Shadow 与 Production
- Shadow榜可以保留研究价值高但尚缺正式买点的公司，用于继续观察与补证据。
- Production发布必须同时满足：`research evidence ready + formal_buy_zone_ready + 合格价格状态`。
- Production Top3必须携带安全/合理买入区；没有正式区间不能进入Production Top3。

## 产业链集中度
- 最终主榜同一Driver原则上不超过2家；
- 同行共振可单独展示，不通过挤占主榜扩大同一链权重。

## Top3
优先顺序：`PRIORITY_INFLECTION > RIGHT_PARTICIPATE > 高质量LEFT_WATCH`。允许少于3只或为空，禁止为了数量降低盈利、估值锚或价格结构标准。

## 输出
V2 Shadow写入`data/research/v2/opportunity_ranking.json`。在历史回放与连续Shadow验证完成前，不覆盖V1正式榜单。Validator必须case-free，不使用固定股票、固定价格或人工历史答案作为PASS条件。
