# 公司盈利研究 Skill

## 目的
把本期所有**已确认盈利改善的产业链**映射到真正受益的主板公司，通过“全链轻筛 → 排除不匹配 → 横向比较 → 跨链去重 → 估值”逐层收敛。计算成本靠轻筛淘汰解决，禁止靠Top-N、每行业配额或先验代表股截断研究准入。

## 输入
1. 本期`coverage_ledger`及全部盈利链resolution；
2. 本期所有满足Manifest `confirmed_improving_chain_definition`的盈利链；
3. Manifest指定的`data/research/company_industry_index.json`，仅用于公司与申万节点映射；
4. 本轮实时获取的公司财报、公告、交易所披露、业绩预告/快报、订单/产销/价格/成本等公开证据。

不得读取上一期公司、估值或机会名单作为召回起点。

## 1. 全链公司轻筛：必须全集进入
对**每一条 confirmed improving chain**，先召回该链对应的全部已映射主板公司，再逐只执行轻量筛选。不得在轻筛前按市值、利润增速、知名度、评分或任何Top-N规则截断。

例如铝盈利链若映射到中国铝业、云铝股份、天山铝业、神火股份等，必须先全部进入轻筛；最终谁被排除只能由公司级证据决定，而不是因为没进“前三名”。

每家公司轻筛至少记录：
- `code / name / source_chain_ids`；
- `business_exposure_match`：主营是否对该Driver有足够实质暴露；
- `profit_driver_match`：本期盈利改善是否确实来自该链Driver，而非其他业务；
- `earnings_quality_match`：扣非、现金流、一次性收益是否支持；
- `comparability`：是否与同链其他公司具有相近经济机制；
- `screen_decision = survive / exclude`；
- `exclusion_reason`；
- `evidence_basis`。

允许排除的原因只使用Manifest列举的公司级原因，并必须有具体证据。不能写“排名靠后”“不是龙头”“暂不关注”。

## 2. 轻筛判断重点
轻筛只回答“有没有资格进入深比较”，不做完整估值。优先检查：
- 主营收入/利润中该产业链暴露是否足够；
- 2026H1/TTM扣非利润是否和行业Driver同向；
- 毛利率/单位利润/产销量是否支持；
- 盈利增长是否主要来自一次性项目；
- 公司是否处于重大重组、主营切换或口径不可比；
- 是否只是概念相关而没有实际利润贡献。

## 3. 横向比较：所有survivor都比较
轻筛后所有`survive`公司必须进入链内横向比较。不得再截Top3或只选代表股。

横向比较维度至少包括：
`业务纯度 / Driver敏感度 / 盈利兑现 / 扣非质量 / 现金流 / 毛利率与成本优势 / 订单或产能可见度 / 持续性 / 资本强度 / 重大口径风险 / 可估值性`。

链内输出：
- `screened_companies`：轻筛全集；
- `excluded_companies`：公司与明确排除原因；
- `compared_companies`：全部survivor；
- `comparison_complete`；
- `fundamental_best`；
- `current_opportunity_best`：加入估值与结构后才确定，可为空；
- `opportunity_resolution_complete`；
- `singleton_reason`：轻筛后只剩1家时说明原因。

## 4. 跨链去重：去重工作量，不丢失链关系
同一公司可能同时属于多个盈利链，例如资源+加工、消费电子+AI终端。横向比较先保留其全部链内身份，之后进入估值前按股票代码去重：
- 一家公司在`valuation_set`只出现一次；
- 必须保留完整`source_chain_ids`；
- 估值只执行一次；
- 估值结果可回填到多个链的机会解析。

去重不能被用来删除某条链的公司覆盖证明。

## 5. valuation_set
所有实际进入`compared_companies`且公司证据验证完成的公司都进入`valuation_set`；按股票代码去重后逐只估值。

轻筛是唯一允许显著降低公司数量的阶段。进入横向比较以后，不得再因为“数量太多”“已有代表股”“计算成本高”跳过估值。

## 6. 守恒诊断
每轮必须能机械回答：
- confirmed improving chain 有多少条；
- 其中多少条完成公司轻筛；
- 未轻筛的盈利链代码/ID是什么；
- 轻筛一共覆盖多少公司；
- 排除多少；
- survivor多少；
- 去重后valuation_set多少。

`unscreened_confirmed_improving_chains`非空时Completion Gate必须失败。

## 7. 每家公司深比较最低证据
`why_now`、`driver_links`与暴露纯度、收入/归母/扣非变化、`margin_quality`、`cashflow_quality`、`one_off_risk`、`forward_bridge`、`evidence_for/evidence_against`、`invalidation_condition`、盈利方向与置信度。

## 持久化
公司研究只写本次`research_state.json`中的`company_light_screen`、`companies`、`chain_comparisons`与`valuation_set`，不建立独立公司池、候选池或Top榜。


## 扣非/核心盈利硬门（schema28 quality fix）
轻筛 survivor 不能只验证归母净利润。必须取得扣非归母净利润或能够等价剥离一次性损益的核心盈利证据，并明确 `core_earnings_trend`。

- 扣非/核心盈利字段缺失时，不得把 `earnings_quality_match` 默认成 true；必须补查公司半年报、业绩预告/快报或交易所公告。
- 若补查后仍不可得，轻筛只能 `exclude:data_unavailable`，不得进入估值。
- 若非经常性损益占归母净利润达到30%及以上，但扣非/核心盈利仍明确改善，公司可以保留为 survivor；但估值盈利桥必须改用扣非/核心盈利，禁止把受污染的归母净利润资本化。
- 若一次性收益主导且核心盈利不改善/无法确认，则 `exclude:nonrecurring_earnings_dominant`。

因此“归母暴增 + 营收平稳 + 扣非字段缺失”本身是补证触发器，不是通过信号。
