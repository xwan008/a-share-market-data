# A股低风险研究 V2 编排 Skill

## 目标
执行唯一主链：
`数据健康 → 346三级Coverage → 盈利景气扫描 → 全部盈利改善链递归拆解 → 链内全部公司轻筛 → survivor横向比较 → 跨链去重 → 逐公司完整估值 → 价格结构 → 买点交集 → Completion Gate`

本Skill不建立周度机会池、候选池、T2池或跨期公司名单。跨期只允许保留行业盈利状态基线。

## 1. DATA HEALTH
确认主板范围、最近完整交易日、最新行情、历史数据和全市场价格结构新鲜。机械数据陈旧时fail closed。

## 2. 周度全量 + 日度增量
周度全量固定扫描申万2021全部346个三级节点；周五18:00为正式刷新锚点。无当前schema有效基线时，下一次可执行研究必须先bootstrap全量基线。

**18:00只是定期刷新锚点，不是基线有效性的资格条件。** 只要某份bootstrap / 手动 / 定时weekly_full结果满足：schema匹配、31/134/346 Coverage完整、盈利发现Gate通过、数据截止日明确、基线未超过Manifest允许的新鲜度，就属于有效行业盈利基线。它可以在06:00、盘前、盘中研究窗口或18:00生成；生成时钟不影响其作为后续公司研究起点的资格。

每个三级节点必须形成：`trend / strength / breadth / confidence / evidence_basis / last_full_scan_date`。禁止统一unconfirmed占位。

日度增量仅继承有效行业基线；对346节点逐一检查新财报、价格/价差、订单、产销、库存、开工、政策等trigger。有触发则重判，无触发显式carry forward。上一期公司、盈利链、估值、机会名单不得作为发现起点。

当已有有效当前schema行业基线时，**早间或手动执行可以直接使用该三级行业基线重新进入公司层**：从所有confirmed improving盈利链重新召回公司、轻筛、横比、去重、估值和买点判断；不得因为基线不是18:00生成而fail closed，也不得复用上一期公司/估值/机会名单代替重新研究。

## 3. COVERAGE LEDGER
运行开始实例化31/134/346全部节点。深研触发继续按Manifest四维规则执行；所有deep节点必须resolution。

## 4. 盈利链：研究准入禁止Top-N
所有`needs_profit_chain_research=true`节点都进入盈利链拆解，直到同链共享直接Driver、领先变量、利润传导和可比业务暴露。

对其中**确认盈利改善**的链：
- 全部进入公司轻筛；
- 禁止只选前10条；
- 禁止每一级行业最多几条；
- 禁止以“重要链排名”决定是否进入公司研究。

Top-N只允许最终展示，不允许作为研究准入。

对deteriorating等非改善deep节点可完成诊断resolution，不必进入机会公司筛选。

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
