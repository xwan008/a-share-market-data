# 公司盈利研究 Skill

## 目的
把本期所有**通过公司准入 Gate 的盈利链**映射到真正受益的主板公司，通过“Company Mapping Gate → 全链轻筛 → 公司级排除 → survivor横向比较 → 跨链去重 → 估值”逐层收敛。

计算成本靠轻筛淘汰解决，禁止靠Top-N、每行业配额、先验龙头或代表股截断研究准入。

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

禁止把“company index 全局 coverage 很高”当作允许静默漏股的理由。

## 2. 全链公司轻筛：全集进入
对**每一条 admitted profit chain**，先召回该链对应的全部已映射主板公司，再逐只执行轻量筛选。不得在轻筛前按市值、利润增速、知名度、评分或任何Top-N规则截断。

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
同一公司可能属于多条盈利链。横向比较先保留全部链内身份，之后进入估值前按股票代码去重：
- 一家公司在 `valuation_set` 只出现一次；
- 必须保留完整 `source_chain_ids`；
- 估值只执行一次；
- 估值/结构/买点结果回填所有相关链。

去重不能用于删除某条链的公司覆盖证明。

## 7. valuation_set
所有完成公司证据验证并进入 `compared_companies` 的公司都进入 `valuation_set`。按股票代码去重后逐只估值。

轻筛是唯一允许显著降低公司数量的阶段。进入横向比较以后，不得因为数量太多、已有代表股或计算成本高而跳过估值。

## 8. 守恒诊断
每轮必须机械回答：
- admitted chain count；
- mapped/screened chain count；
- unscreened admitted chain IDs；
- unresolved in-scope company mappings；
- 轻筛公司总数；
- 排除数；
- survivor数；
- 去重后 valuation_set 数。

只要 `unscreened_admitted_chains` 或 `unresolved_in_scope_company_mappings` 非空，Completion Gate 必须失败。

## 9. 每家公司深比较最低证据
至少包含：`why_now / driver_links / business_exposure / revenue_and_core_profit_change / margin_quality / cashflow_quality / one_off_risk / forward_bridge / evidence_for / evidence_against / invalidation_condition / earnings_direction / confidence`。

## 10. 持久化
公司研究只写最近一次通过Completion Gate的 `data/research/research_state.json`，不建立独立公司池、候选池、Top榜、估值缓存或跨期Near-miss池。
