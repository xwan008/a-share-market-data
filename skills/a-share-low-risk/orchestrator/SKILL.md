# A股低风险研究 V2 编排 Skill

## 目标
执行唯一主链：
`数据健康 → 全市场景气发现（31一级+134二级） → 景气方向完整展开 → 相关三级行业盈利验证 → 盈利链递归拆解 → 链内全部公司轻筛 → survivor横向比较 → 跨链去重 → 逐公司完整估值 → 价格结构 → 买点交集 → Completion Gate`

核心原则：**先发现最近哪里正在变好，再验证这些方向下面哪些三级盈利链真的改善，最后才找公司。**

本Skill不建立周度机会池、候选池、T2池或跨期公司名单。跨期只允许保留“全市场景气发现 + 已验证三级盈利状态”的市场基线，不能保留公司发现种子。

## 1. DATA HEALTH
确认主板范围、最近完整交易日、最新行情、历史数据和全市场价格结构新鲜。机械数据陈旧时fail closed。

## 2. 第一层：全市场景气发现
每次weekly_full先轻量扫描申万2021全部31个一级行业和134个二级行业，回答：**最近哪些行业的真实经营景气正在改善？**

这里不先看公司，也不从上期机会名单、熟悉板块或当日涨幅反推行业。优先证据包括：行业利润/利润率、产品价格或价差、库存、开工率/产能利用率、订单/出货/销量/产量、进出口/供需、代表性公司经营数据，以及真正改变供需或成本的政策。

行业指数涨幅、ETF强弱和市场情绪可以做辅助验证，但不能作为“景气改善”的第一证据。

所有31+134都必须被检查；**禁止Top-N或固定数量截断。** 化工、煤炭、有色、电力设备等只要本期证据达到规则，就全部进入下一层，不得因为已有3个方向就停止。

对每个一级/二级行业记录：`trend / strength / breadth / confidence / leading_variables / evidence_basis / recent_change_window / selected_for_level3_verification / selection_reason`。

## 3. 第二层：景气方向向三级完整下钻
景气发现层不是最终结论，只决定“哪里值得做昂贵的三级盈利验证”。

下钻规则：
- 二级行业 `trend=improving`：该二级行业下**全部三级行业**进入盈利验证；
- 二级行业 `breadth=selective/divergent`：必须向三级拆开验证，不能因为二级整体不整齐而放弃；
- 若一级行业已明显 `improving/selective/divergent`，但二级证据不足以定位具体方向，则该一级行业下**全部三级行业**进入验证，防止遗漏；
- 任何入选方向不得只挑“最强3个三级行业”。

未被景气发现层选中的三级节点仍要在taxonomy ledger中有routing记录，但不要求本期逐一做完整盈利研究；这和“遗漏”不同，因为它们已经被上层景气扫描明确路由为“本期不下钻”。

## 4. 第三层：三级盈利验证与盈利链拆解
对所有被展开的三级行业逐一研究真实盈利状态，形成：`trend / strength / breadth / confidence / evidence_basis / leading_variables / profit_driver`。

这里才回答：**大行业最近变好之后，究竟是下面哪些三级产业链真的在赚钱/利润改善？**

- 三级 `trend=improving`：必须进入盈利链递归拆解，确认Driver、领先变量、利润传导、Forward Bridge和失效条件；
- `deteriorating` 或明显 `divergent`：可做诊断拆解，但不能直接进入机会公司筛选；
- 只有 `verified level3 improving + resolved profit chain + confirmed profit transmission` 才允许进入公司层。

例如“基础化工景气改善”只表示值得下钻；真正进入公司层的可以是农药、氟化工、磷化工、轮胎材料等其中已被证据确认利润改善的三级链。煤炭同理，先确认煤炭大方向，再区分动力煤、焦煤等具体盈利链。

日度增量时仍检查全部31一级+134二级的新触发。若出现新的景气方向，当天就展开对应全部三级行业；已有基线方向无新增触发可carry forward。上一期公司、估值和机会名单不得作为本期发现起点。

## 5. 全链公司轻筛
每条confirmed improving chain先从本期公司映射召回**全部对应主板公司**，再逐只轻量检查：
`业务暴露 / 盈利Driver匹配 / 扣非与现金流质量 / 一次性收益 / 可比性 / 重大口径风险`。

排除只能基于公司级证据，并记录明确`exclusion_reason`。不能因为排名低、不是龙头、数量太多而排除。

例如铝链存在中国铝业、云铝股份、天山铝业、神火股份等时，必须先全部轻筛；只有盈利改善不是由铝Driver贡献、业务暴露不足或经济机制不可比等证据，才允许淘汰。

## 6. survivor横向比较 + 去重
轻筛后所有survivor必须进入横向比较，不得再Top3截断。

比较：业务纯度、Driver敏感度、盈利兑现、扣非/现金流、成本优势、订单/产能、持续性、资本强度、重组/一次性风险、可估值性。

同一股票若属于多条盈利链，先保留全部链内比较关系，再在进入估值前按股票代码去重：
- `valuation_set`只出现一次；
- 保留全部`source_chain_ids`；
- 估值只做一次；
- 结果回填所有相关链。

计算成本靠轻筛和去重降低，不靠研究截断降低。

## 7. 公司守恒Gate
进入估值前必须机械满足：
`confirmed improving chains = 已完成公司轻筛的改善链 + 明确无可用主板公司的改善链`。

并输出：
- confirmed improving chain count；
- screened chain count；
- unscreened chain IDs；
- 轻筛公司总数；
- 排除数；
- survivor数；
- 去重后valuation_set数。

`unscreened_confirmed_improving_chains`非空时直接fail closed。

## 8. VALUATION：先审口径，再算价值
valuation_set每家公司执行valuation Skill完整流程。

特别硬门：
1. Forward EPS前检查当前股本与重大公司行动；
2. 股本重大变化时禁止历史EPS直接乘增长率；
3. 资源/订单周期公司禁止把短期高增长直接配成长PE；
4. 估值出现极端偏离时强制独立第二模型、股本复核和周期/增长持续性复核；
5. 第二模型无法支持则`review_required:model_instability`，不能把极端低估直接当机会。

## 9. PRICE STRUCTURE：独立生成入场区间
价格结构只回答WHEN。对每家非review估值公司输出独立的`structure_entry_range`和`structure_invalidation`，不得参考合理/安全价值调整技术区间。

## 10. BUY POINT：价值与结构求交集
每家完整非review公司都必须生成`buy_point_assessment`：
- `value_eligible`；
- `timing_eligible`；
- `structure_entry_range`；
- `buy_price_range = safe_price_range ∩ structure_entry_range`；
- `buy_point_status`；
- `invalidation_price`；
- `buy_point_basis`。

只有：
`value_eligible=true + timing_eligible=true + buy_price_range非空`
才允许`buyable_now`并进入【当前买点】。

`damaged/overheated`禁止buyable_now；没有交集就等待，绝不扩张安全区或技术区制造买点。

## 11. COMPLETION GATE
Gate前必须满足：
- Coverage exact；
- 所有deep节点resolved；
- 所有confirmed improving chain完成公司轻筛；
- 无任何研究准入Top-N/每行业配额截断；
- 所有轻筛survivor完成横向比较；
- valuation_set按股票代码去重且保留全部链关系；
- valuation_set逐只完整估值；
- 所有极端估值偏离完成第二模型审计或进入review；
- 所有非review公司完成买点评估；
- 当前机会只来自`buyable_now`。

任一失败：`status=incomplete_research`，不发布新的当前买点，也不得用不完整state覆盖上一份有效完整state。

## 持久化
只写`data/research/v2/research_state.json`。严禁独立周度Top榜、候选池、公司池、机会池和跨期估值缓存。

## 展示
固定输出：执行状态、全市场盈利景气雷达、完整盈利产业链雷达、链内公司轻筛与横向比较、估值与价格区间、价格结构与时机、当前买点、诊断。


## 接近买点榜（Near-miss Ranking）

【当前低风险买点】继续只允许 `buy_point_status=buyable_now`，不得为了凑榜降低价值、安全边际、结构或交集门槛。

但只要存在完成估值且非 `review_required` 的公司，每次正式输出都必须同时生成【接近买点榜】，默认展示前10名；即使当前买点为0，也不得只输出空列表或一句“暂无买点”。该榜只做当期展示排序，不得持久化为候选池、机会池或下一轮发现种子。

对全部完成估值且非review公司计算：
- `missing_hard_conditions`：`value_eligible=false` +1；`timing_eligible=false` +1；安全价区与结构入场区无交集 +1；若已有交集但当前价不在交集内 +1；`avoid` 额外 +1风险门惩罚。
- `value_gap_pct`：当前价高于安全价上沿时，计算降到安全价上沿所需百分比；已满足价值条件则为0。
- `structure_gap_pct`：当前价距离独立 `structure_entry_range` 最近边界的百分比；已位于结构入场区则为0；无有效结构入场区则记为不可测并排在可测者之后。
- `safe_structure_range_gap_pct`：安全价区与结构入场区不相交时，计算两区间最近边界的百分比距离；已有交集则为0。
- `current_to_intersection_pct`：两区间已有交集时，计算当前价距离交集最近边界的百分比；当前价已在交集内则为0。

固定排序为：`avoid_penalty`升序 → `missing_hard_conditions`升序 → `safe_structure_range_gap_pct`升序（不可测最后） → `current_to_intersection_pct`升序（不可测最后） → `value_gap_pct + structure_gap_pct`升序 → 基本面横比得分降序 → 股票代码升序。

每个上榜公司必须明确写出【当前还缺什么】和【下一触发条件】。第1名只表示“离现有低风险买点规则最近”，不表示预期收益最高，也不等于现在可以买。
