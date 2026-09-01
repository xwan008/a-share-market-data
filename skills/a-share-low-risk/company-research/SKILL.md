# 公司盈利研究 Skill

## 目的
把本期所有**通过公司准入 Gate 的盈利链**映射到真正受益的主板公司，通过“Company Mapping Gate → 全链轻筛 → 公司级排除 → survivor横向比较 → 估值准入 → 跨链去重 → 估值”逐层收敛。

计算成本靠轻筛与估值准入的绝对质量门淘汰解决，禁止靠Top-N、每行业配额、先验龙头或代表股截断研究准入。

## 输入
1. 本期Prompt全市场景气发现及taxonomy映射；
2. 本期三级行业盈利状态；
3. 所有满足公司准入规则的 admitted profit chains：
   - `trend=improving`；或
   - `trend=stable AND breadth=divergent`；
4. `data/research/company_industry_index.json`；
5. 本轮实时获取的公司财报、公告、交易所披露、业绩预告/快报、订单/产销/价格/成本等公开证据。

不得读取上一期公司、估值、买点或Near-miss名单作为召回起点。

## 1. Company Mapping Gate
公司全集轻筛之前，必须先检查公司行业映射完整性。

对 `company_industry_index.json` 中全部 missing/unmapped 股票逐一判断是否可能属于本轮 admitted Level-3 / profit chain：
- 明确不属于本轮范围：记录为 `out_of_scope_mapping_gap` 后可继续；
- 可能属于本轮范围：必须补查行业归属；
- 仍无法解析且可能影响本轮公司全集：记录 `unresolved_in_scope_mapping`，Completion Gate失败。

若查询公司时发现其已退市、被吸收合并、当前无有效交易或其他当前不可作为交易标的的状态，直接 `skip/inactive`，不进入 Mapping Gate，也不影响 Completion Gate。

禁止把“company index 全局 coverage 很高”当作允许静默漏股的理由。

## 2. 全链公司轻筛：全集进入
对**每一条 admitted profit chain**，先召回该链对应的全部当前有效、已映射主板公司，再逐只执行轻量筛选。不得在轻筛前按市值、利润增速、知名度、评分或任何Top-N规则截断。

每家公司至少记录：
- `code / name / source_chain_ids`；
- `business_exposure_match`：主营是否对该Driver有实质暴露；
- `profit_driver_match`：本期盈利变化是否确实与该链Driver一致；
- `earnings_quality_match`：扣非/核心盈利、现金流、一次性损益是否支持；
- `comparability`：经济机制是否与同链公司可比；
- `screen_decision = survive / exclude`；
- `exclusion_reason`；
- `evidence_basis`。

排除只能使用Manifest允许的公司级原因，并必须有具体证据。不能使用“排名靠后”“不是龙头”“暂不关注”“数量太多”。

## 3. stable + divergent 的处理
`stable + divergent` 进入公司层的目的，是捕捉**行业总体稳定、但内部公司盈利开始分化**的结构性机会。

这类链：
- 公司召回和轻筛要求与 improving 链完全相同；
- 必须证明 survivor 的公司级 Driver/核心盈利确实改善或明显优于同链；
- **不得因为是 divergent 分支而降低估值安全边际、技术结构或 buyable_now 标准**。

如果没有公司级证据证明真实分化，则该公司不能仅凭行业 `breadth=divergent` 进入估值。

## 4. 扣非/核心盈利硬门
轻筛 survivor 不能只验证归母净利润。必须取得扣非归母净利润或能够等价剥离一次性损益的核心盈利证据，并明确 `core_earnings_trend`。

- 字段缺失时，不得把 `earnings_quality_match` 默认成 true；必须补查半年报、业绩预告/快报或交易所公告；
- 补查后仍不可得，只能 `exclude:data_unavailable`；
- 若非经常性损益占归母净利润达到30%及以上，但扣非/核心盈利仍明确改善，可保留 survivor，但估值盈利桥必须改用扣非/核心盈利；
- 若一次性收益主导且核心盈利不改善/无法确认，`exclude:nonrecurring_earnings_dominant`。

“归母暴增 + 营收平稳 + 扣非缺失”是补证触发器，不是通过信号。

## 5. 横向比较：所有 survivor 都比较
轻筛后所有 `survive` 公司必须进入链内横向比较，不得再截Top3或只选代表股。

比较维度至少包括：
`业务纯度 / Driver敏感度 / 盈利兑现 / 扣非质量 / 现金流 / 毛利率与成本优势 / 订单或产能可见度 / 持续性 / 资本强度 / 重大口径风险 / 可估值性`。

每条链输出：
- `screened_companies`；
- `excluded_companies`及原因；
- `compared_companies`：全部 survivor；
- `comparison_complete`；
- `fundamental_best`；
- `singleton_reason`（若仅剩1家）。

## 6. 跨链去重：去重工作量，不丢链关系
同一公司可能属于多条盈利链。横向比较先保留全部链内身份，之后按股票代码去重：
- 必须保留完整 `source_chain_ids`；
- 去重后只对同一公司做一次估值准入判断；
- 若进入估值，估值只执行一次；
- 估值/结构/买点结果回填所有相关链。

去重不能用于删除某条链的公司覆盖证明。

## 7. 估值准入 Gate 与 valuation_set
完成轻筛和横向比较后，公司**不会因为已经是 survivor 就自动进入完整估值**。

只有同时满足以下四个绝对条件，才进入 `valuation_set`：
1. **公司级 Driver 明确**：本期盈利变化确实由本轮盈利链的 Driver 驱动，业务暴露与利润传导清楚；
2. **扣非/核心盈利改善**：核心盈利方向明确改善，不能仅靠归母利润或一次性收益；
3. **现金流/盈利质量合格**：经营现金流、利润质量和一次性损益支持盈利改善；银行、保险等特殊商业模型使用其适用的资产负债表、资本质量和核心盈利指标替代普通经营现金流判断；
4. **持续性足够**：订单、价格/价差、成本优势、产能利用、需求或其他 Forward Bridge 能支持盈利改善不是单季偶发。

任一条件不满足，就不进入完整估值，并记录 `valuation_admission_exclusion_reason`。

这个 Gate **禁止Top-N、固定数量、每行业配额或“只估龙头”**。只看绝对质量条件，因此可能有0只，也可能有很多只通过。

所有通过 Gate 的公司按股票代码去重进入 `valuation_set`，保留完整 `source_chain_ids`，并逐只执行完整估值。

## 8. 守恒诊断
每轮必须机械回答：
- admitted chain count；
- mapped/screened chain count；
- unscreened admitted chain IDs；
- unresolved in-scope company mappings；
- 轻筛公司总数；
- 排除数；
- survivor数；
- 完成横向比较数；
- 估值准入通过数与排除数；
- 去重后 valuation_set 数。

只要 `unscreened_admitted_chains` 或 `unresolved_in_scope_company_mappings` 非空，Completion Gate 必须失败。所有 survivor 必须完成横向比较和估值准入判断，但只有通过估值准入 Gate 的公司才要求完成完整估值。

## 9. 每家公司深比较最低证据
至少包含：`why_now / driver_links / business_exposure / revenue_and_core_profit_change / margin_quality / cashflow_quality / one_off_risk / forward_bridge / evidence_for / evidence_against / invalidation_condition / earnings_direction / confidence`。

## 10. 持久化
公司研究只写最近一次通过Completion Gate的 `data/research/research_state.json`，不建立独立公司池、候选池、Top榜、估值缓存或跨期Near-miss池。
