# A股低风险研究 V2 编排 Skill

## 目标
执行唯一主链：
`数据健康 → Prompt全市场景气搜索 → 景气方向taxonomy映射 → 相关三级行业盈利验证 → 盈利链递归拆解 → 链内全部公司轻筛 → survivor横向比较 → 跨链去重 → 逐公司完整估值 → 价格结构 → 买点交集 → 接近买点榜 → Completion Gate`

核心原则：**发现阶段广而轻，验证阶段窄而深。** 景气发现是搜索问题，三级盈利验证才是结构化状态问题。

跨期只允许保留“景气方向 + 已验证三级盈利状态”的市场基线。一级/二级行业只承担taxonomy路由，不维护逐项景气状态；上一期公司、估值、机会和接近买点榜不得成为下一轮发现种子。

## 1. DATA HEALTH
确认主板范围、最近完整交易日、最新行情、历史数据和全市场价格结构新鲜。机械数据陈旧时fail closed。

## 2. 第一层：Prompt全市场景气搜索
weekly_full直接基于当前公开证据做一次全市场搜索，回答：**最近1~3个月哪些A股对应产业的真实经营景气正在改善，或者出现足以值得三级盈利验证的明确拐点？**

这是广而轻的Prompt研究，不建立31个一级+134个二级行业逐项状态表。搜索时必须主动覆盖资源/能源、化工/材料、制造/设备、科技、消费、医药、金融地产、公用事业/交通运输、农业等主要经济板块，不能只从熟悉方向、旧名单或当日热点出发，也不能发现几个方向后提前停止。

优先证据：行业利润/利润率、产品价格或价差、库存、开工率/产能利用率、订单/出货/销量/产量、进出口/供需、代表性公司经营数据，以及真正改变供需或成本的政策。板块涨幅、ETF强弱和市场情绪只能辅助，不能成为景气第一证据。

输出只保存真正被识别出的景气方向，每个方向记录：`direction_name / taxonomy_refs / recent_change_window / why_now / leading_variables / evidence_basis / falsifiers`。**禁止Top-N或固定数量截断。**

## 3. 第二层：景气方向映射到三级行业
景气方向只是研究入口，不直接筛股票。使用申万taxonomy把每个方向映射到相关一级/二级/三级节点。

若方向映射到一级或二级行业，必须展开与该景气逻辑相关的全部三级子行业，不能只挑表现最强的几个；例如Prompt发现“煤炭景气改善”，要继续验证动力煤、焦煤等相关三级；发现“基础化工改善”，要向下定位哪些化工三级链真正受益。

未被本次景气搜索覆盖的三级行业只保留taxonomy routing，不要求当期做完整盈利研究，这不属于遗漏。

## 4. 第三层：三级盈利验证与盈利链拆解
只对被景气方向映射出的相关三级行业逐一做真实盈利验证，形成结构化状态：`trend / strength / breadth / confidence / evidence_basis / leading_variables / profit_driver`。

- `trend=improving`：必须继续拆出真实盈利链，确认Driver、领先变量、利润传导、Forward Bridge和失效条件；
- `deteriorating`或明显`divergent`：可保留诊断，但不能直接进入公司机会筛选；
- 只有`verified level3 improving + resolved profit chain + confirmed profit transmission`才允许进入公司层。

周度基线只保存：**本周Prompt识别出的景气方向 + 这些方向下已验证的三级盈利状态**。

日度增量不重做全市场状态矩阵，只用Prompt搜索过去约24小时新增证据：是否新增景气方向、已有方向是否失效/增强、已验证三级盈利状态是否需要改变。有触发才更新相关链；无实质变化就carry forward。

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

## 8. VALUATION：经济价值驱动优先
valuation_set每家公司执行 Valuation Engine V2。

硬门：
1. 先识别 `valuation_archetype`，申万一级行业不能单独决定模型；
2. 非review公司必须有 `base_case + downside_case + base_fair_value + safe_price_ceiling`；
3. resource_asset 禁止固定低PE单模型，必须使用NAV/DCF、正常化EV/EBITDA、FCF/股息能力等资产/现金流方法；
4. spread_cyclical 必须显式研究产品-原料价差、开工与正常化利润率；
5. financial 必须执行PB-ROE或Residual Income；
6. 正常化必须反映已发生的产能、资源量、产品结构变化，不能机械回归旧年度利润；
7. 极端偏离的第二模型必须更换价值驱动家族，同一EPS换另一个PE倍数不算独立模型；
8. 安全价硬边界是 `safe_price_ceiling`，MOS只作用一次，禁止“压盈利+低倍数+再折合理价下沿”的重复保守化。

## 9. PRICE STRUCTURE：独立生成入场区间
价格结构只回答WHEN。对每家非review估值公司输出独立的`structure_entry_range`和`structure_invalidation`，不得参考合理/安全价值调整技术区间。

## 10. BUY POINT：价值与结构求交集
每家完整非review公司都必须生成`buy_point_assessment`：
- `value_eligible`；
- `timing_eligible`；
- `structure_entry_range`；
- `buy_price_range = structure_entry_range ∩ (-∞, safe_price_ceiling]`；
- `buy_point_status`；
- `invalidation_price`；
- `buy_point_basis`。

只有：
`current_price <= safe_price_ceiling + timing_eligible=true + buy_price_range非空`
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


## 接近买点榜（Near-miss Ranking V2）

【当前低风险买点】仍只允许 `buyable_now`，绝不为了凑榜降低价值或结构门槛。

Near-miss 的含义改为：**距离成为可执行买点还需要多大实际变化**，而不是旧版按区间字段字典序排序。

对所有完整非review且非avoid公司计算：
- `value_gap_pct`：当前价下降到 `safe_price_ceiling` 所需幅度；已价值合格为0；
- `structure_gap_pct`：当前价到有效结构入场区最近边界的距离；
- `ceiling_structure_gap_pct`：结构入场区整体高于安全上限时，两者最近边界距离；若结构区已有部分位于安全上限以内则为0；
- `current_to_actionable_range_pct`：有效可执行区存在时，当前价到该区最近边界距离；
- `action_distance_pct = max(上述可测硬距离)`，表示当前最大的阻塞距离；
- `valuation_confidence_penalty`：估值不确定性越高，排序越靠后。

距离标签：
- `near`：<=5%；
- `watch`：>5%且<=15%；
- `far`：>15%。

排序：`near_miss_tier → action_distance_pct → valuation_confidence_penalty → 基本面得分 → 股票代码`。

Top10仍必须输出；如果最接近的公司也超过15%，必须明确写“相对最接近，但仍远离买点”，不能把35%、60%的价值缺口包装成“接近买点”。

该榜只做当期展示，不得持久化为候选池或下一轮发现种子。
