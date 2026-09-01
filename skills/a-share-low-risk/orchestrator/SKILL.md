# A股低风险研究编排 Skill

## 目标
执行唯一正式主链：

`DATA GATE → Prompt全市场轻召回 → taxonomy映射 → 三级行业盈利状态刷新 → 公司准入Gate → 盈利链解析 → Company Mapping Gate → 链内全部公司轻筛 → survivor横向比较 → 跨链去重 → 估值 → 独立价格结构 → 买点交集 → 接近买点榜 → Completion Gate → 正式发布`

核心原则：**发现阶段广而轻，验证阶段窄而深；价值与时机独立；任何硬门失败都 fail closed。**

本 Skill 只服从 `config/research_runtime_policy.json` 和 `config/research_pipeline_manifest.json` 的正式生产契约，不使用数字 schema、shadow、V2/V3 等版本标签作为运行条件。

## 1. DATA GATE
正式研究开始前先确定“最近一个已经完成的A股交易日”，读取 `data/health.json` 并验证：
- `health.trade_date` 等于预期交易日；
- `market_status=closed`；
- 数据源 errors 为空；
- 行情覆盖没有实质退化；
- 历史数据已覆盖该交易日；
- `full_market_price_structure.json` 的参考交易日与之相同。

任一失败：输出 `data_stale_or_incomplete`，不得发布新的正式买点，也不得覆盖上一份有效 `industry_state.json` 或 `research_state.json`。

## 2. Prompt全市场轻召回：每次都重新看市场
每次运行都基于当前公开证据，从全市场做一次**轻量、开放式召回**。不能把上一次景气方向、公司、估值、Near-miss 或已有关注名单当成搜索边界。

必须主动覆盖：资源能源、化工材料、制造设备、科技、消费、医药、金融地产、公用事业/交通运输、农业等主要经济领域。不能发现几个方向以后提前停止，也不能做Top-N截断。

优先证据：行业收入利润/利润率、产品价格与价差、库存、开工率/产能利用率、订单/出货/销量/产量、进出口/供需、代表性公司经营数据，以及真正改变供需或成本的政策。板块涨幅和ETF强弱只能辅助，不能成为盈利景气第一证据。

输出当期识别出的所有有效景气方向及：`direction_name / taxonomy_refs / why_now / leading_variables / evidence_basis / falsifiers`。

## 3. taxonomy映射与三级盈利状态
景气方向不是股票名单。每个方向必须映射到申万2021 taxonomy；若映射到一级/二级节点，继续展开到**所有与该盈利逻辑相关的三级行业**。

一级/二级只做路由，不保存长期景气标签。真正的跨期产业状态只存在于三级行业。

### 周度与日度的边界
- Prompt全市场轻召回：**每次运行都做**。
- 三级行业深度盈利刷新：周度全量、日度增量。
- 周五18:00对本轮发现方向映射出的全部相关三级行业重新验证；失败则下一个可用工作日18:00补做。
- 其他运行读取最近有效 `industry_state.json`，只对存在新证据、新方向、失效或实质变化的三级节点做深度增量刷新。

因此“每日增量”只限制三级深研工作量，**不能限制Prompt发现范围**。

三级状态至少记录：`trend / strength / breadth / confidence / evidence_basis / leading_variables / profit_driver / falsifiers / last_verified_at`。

## 4. 公司准入 Gate
三级行业进入公司层只有两种情况：
1. `trend=improving`；
2. `trend=stable AND breadth=divergent`。

第二种只代表行业内部出现可研究的结构性分化，**只扩大研究资格，不降低任何估值、价格结构或买点标准**。

`deteriorating`、`unconfirmed`、`stable + 非divergent`不进入公司机会研究。

进入公司层之前必须把行业逻辑拆成 resolved profit chain，确认：Driver、领先变量、利润传导、Forward Bridge 与失效条件。没有确认利润传导的方向不能仅凭概念相关进入公司层。

## 5. Company Mapping Gate
在公司轻筛前读取 `data/research/company_industry_index.json`。

公司索引即使全局状态为 degraded，也不能简单停止整个研究；必须检查所有 missing/unmapped 股票是否可能属于**本轮已准入三级行业/盈利链**：
- 明确不在本轮准入范围：记录诊断后可继续；
- 可能在本轮范围但尚未解析：必须补查映射；
- 仍无法解析且可能影响本轮公司全集：`incomplete_research`，禁止静默漏股。

## 6. 全链公司轻筛
对每一条 admitted profit chain，从公司索引召回全部对应主板公司，再逐只轻筛。不能在轻筛前按市值、知名度、龙头、评分或Top-N截断。

轻筛至少检查：业务暴露、Driver匹配、扣非/核心盈利、现金流、一次性损益、可比性和重大口径变化。排除必须基于公司级证据并记录 `exclusion_reason`。

扣非/核心盈利缺失时不得默认通过；必须补查公开证据。若仍不可得，只能 `exclude:data_unavailable`。一次性收益主导而核心盈利没有改善时排除。

## 7. survivor 横向比较与跨链去重
所有轻筛 survivor 都进入横向比较，不得再截Top3。

比较：业务纯度、Driver敏感度、盈利兑现、扣非/现金流、毛利率与成本优势、订单/产能可见度、持续性、资本强度、重大口径风险、可估值性。

同一股票属于多条盈利链时，先保留全部链内比较关系，再按股票代码去重进入 `valuation_set`；必须保留全部 `source_chain_ids`。

## 8. 估值：默认简单，异常升级
正常盈利公司固定走相对盈利估值：

`核心盈利 → Forward核心EPS → 当前/TTM PE + 动态PE → 三级同行PE → 核心盈利增速调整 → PB/ROE交叉验证 → 180日市场sanity → fair PE区间 → reasonable price → base fair value → 一次MOS → safe_price_ceiling`

只有Manifest规定的异常触发条件出现时才进入 PB-ROE / Residual Income / EV-EBITDA / NAV/DCF / FCF/DCF 等Exception Path，并必须记录 `exception_trigger`。

MOS只应用一次：`safe_price_ceiling = base_fair_value × (1-MOS)`。

## 9. 价格结构：独立回答 WHEN
全市场机械价格结构独立于基本面运行。对每家完整非review估值公司读取/生成：`structure_type / structure_entry_range / structure_invalidation / key_level / relative_strength / volume_confirmation / chase_risk / timing_action`。

技术区间不得参考合理价或安全价反向调整。

## 10. BUY POINT：价值 × 结构
每家完整非review公司都必须生成买点评估：
- `value_eligible = current_price <= safe_price_ceiling`；
- `timing_eligible`来自独立价格结构；
- `buy_price_range = structure_entry_range ∩ (-∞, safe_price_ceiling]`。

只有价值合格、结构合格、交集非空且当前价位于可执行区间，才允许 `buyable_now`。

`damaged / overheated`永远不能成为当前低风险买点。没有交集就等待，不能扩大价值区或技术区制造买点。

## 11. 接近买点榜
正式买点仍只允许 `buyable_now`，绝不为了凑榜降低门槛。只要存在可评估的非review公司，即使当前买点为0，也输出Top10 Near-miss。

距离字段：
- `missing_hard_conditions`：价值未满足 +1，结构未满足 +1；
- `value_gap_pct`；
- `structure_gap_pct`；
- 两者可测时 `action_distance_pct=max(value_gap_pct, structure_gap_pct)`。

标签：near≤5%，watch>5%且≤15%，far>15%。排序：`missing_hard_conditions → distance_band → action_distance_pct → fundamental_score → stock_code`。结构距离不可测者在同一缺失条件桶中排在可测者之后。

每只只需明确【还缺什么】和【下一触发条件】；第1名若仍>15%，注明“相对最接近，但仍远离买点”。Near-miss只用于当期展示，不得成为跨期候选池或下一轮发现种子。

## 12. COMPLETION GATE 与正式发布
正式发布前必须机械确认：
- Data Gate通过；
- 本轮Prompt全市场轻召回完整，无Top-N截断；
- 所有发现方向完成taxonomy映射；
- 所有需要刷新的三级行业盈利状态完成；
- 所有 admitted chains 完成Driver/利润传导解析；
- Company Mapping Gate通过；
- 所有 admitted chains 完成公司全集轻筛；
- 所有 survivor 完成横向比较；
- valuation_set 去重且保留全部链关系；
- valuation_set逐只完成估值或明确进入review；
- 所有非review公司完成价格结构、买点评估和Near-miss距离；
- 【当前买点】只来自 `buyable_now`。

任一失败：`status=incomplete_research`，不发布新的正式买点，且不得覆盖上一份有效正式状态。

## 13. 持久化边界
只允许：
- `data/research/industry_state.json`：紧凑的三级行业跨期盈利基线，是唯一跨期基本面记忆；
- `data/research/research_state.json`：最近一次通过全部Gate的完整正式研究结果；
- `data/research/full_market_price_structure.json`：全市场机械价格结构。

禁止独立候选池、机会池、周榜缓存、Near-miss池和单独估值缓存。旧 `data/research/v2/*` 不再作为运行输入。

## 14. 正式输出
固定输出：
`【执行状态】 / 【全市场景气发现】 / 【三级行业盈利状态】 / 【产业链与公司轻筛】 / 【估值与安全价】 / 【价格结构与时机】 / 【当前买点】 / 【接近买点榜】 / 【诊断与失效条件】`。
