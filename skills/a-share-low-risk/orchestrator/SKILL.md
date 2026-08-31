# A股低风险研究 V2 编排 Skill

## 目标
执行唯一主链：
`数据健康 → 全市场Coverage逐节点台账 → 当期公开盈利证据 → 盈利链递归拆解 → 链内公司比较 → 分类估值 → 价格结构 → Completion Gate → 当前机会`

18:00每次从当前全市场重新开始，不从上一期行业、公司或机会名单开始，也不建立周度池、候选池或跨期机会缓存。上一份有效state只用于06:00增量复核和防止不完整新结果覆盖有效旧结果。

## 数据与证据边界
Manifest `authoritative_data`只约束仓库中允许长期读取的机械数据。18:00必须主动使用当前公开证据完成基本面研究，包括公司财报/公告、交易所披露、官方统计、行业协会/产业数据、产品价格与价差、订单/出货/产销、库存/开工/产能利用率，以及必要的可信新闻/研究资料。公开证据只服务本次研究，不得整理成跨期候选池或周度机会池。

## 1. DATA HEALTH
确认主板范围、最近完整交易日、最新行情、历史数据和全市场价格结构足够新鲜；机械行情数据陈旧时fail closed。公开证据不足只影响对应节点，不得等同于“没有机会”。

## 2. COVERAGE LEDGER：先建台账，再做发现
读取`config/industry_scan_universe.json`，在任何景气判断之前，把申万2021全部31个一级、134个二级、346个三级节点逐一实例化到`research_state.coverage_ledger`。

每个节点必须唯一记录：
`code / name / level / parent_code / accounted_for / status / scan_depth / evidence_scope / evidence_basis / needs_profit_chain_research / profit_chain_resolution`。

`accounted_for=true`只表示该节点本期确实被检查并形成可审计状态，不代表完成深度研究。只有记录存在且status、scan_depth、evidence_scope、evidence_basis均非空，才可计入accounted_for。

允许状态：`strong_improving / improving / stable / weak / deteriorating / divergent / unconfirmed / not_applicable`。

- `stable / weak / unconfirmed / not_applicable`可浅扫；
- `strong_improving / improving / deteriorating / divergent`必须`scan_depth=deep`，且`needs_profit_chain_research=true`；
- `parent_supported`只允许浅扫节点使用；只要出现节点级强化、恶化或分化证据，就必须升级为直接/横截面证据和deep；
- 禁止用“能源金属/半导体/航海装备”等合并方向替代多个申万节点记录；
- 最终31/134/346计数必须从ledger机械派生，禁止手填，也禁止`null`或统一占位符作为missing列表。

## 3. 当期公开盈利证据与全市场发现
对ledger全部节点完成状态判断。弱/稳定节点允许用父级+本节点无明显反向信号做浅扫；改善、恶化、分化节点必须使用本节点或足够可比的横截面当前证据深研。

至少关注收入/利润、毛利率/利润率、产品价格/价差、订单/出货/销量/产量、库存/开工/产能利用率、出口/资本开支及行业特有领先变量。禁止从熟悉股票、上一期机会或当前对话曾出现的行业开始倒推。

## 4. PROFIT CHAIN DECOMPOSITION
所有`needs_profit_chain_research=true`的Coverage节点必须进入盈利链研究。继续拆分直到同链公司基本共享：
1. 直接盈利Driver；
2. 领先变量；
3. 利润传导机制；
4. 可比业务暴露。

任一不满足继续按产品/服务、工艺路线、应用场景、客户需求、原料成本、供需/价格/价差等拆分。任何`must_split/continue_split`必须在本次结束前拆完；若公开证据确实不足，只能以`unconfirmed_with_evidence_gap`结束并明确缺口，不得留下开放状态。

每个deep Coverage节点最终必须有`profit_chain_resolution = resolved`或`unconfirmed_with_evidence_gap`，并能关联到具体chain_id。

## 5. CHAIN COMPANY COMPARISON + COMPANY RESEARCH
只从本期已确认盈利链出发识别主板受益公司，再按`company-research` Skill验证。

若同一盈利链存在2家及以上经济机制真正可比的主板公司，必须至少比较2家并完成横向比较后才能进入最终估值。不得找到第一家代表股就继续往下。若确实只有一家高纯度主板公司，必须写明`singleton_reason`。

每条重点链必须形成：`compared_companies / comparison_complete / fundamental_best / current_opportunity_best / opportunity_resolution_complete`。`current_opportunity_best`允许为空。

## 6. VALUATION
按`valuation` Skill执行。完整估值桥必须从盈利基础推到合理价格与安全价格；当前价格只能用于比较，不能反向进入内在价值计算。

若公司只能得到`review_required`，该公司不能成为可发布当前机会；但只要明确说明为何无法可靠估值，并将该链解析为“当前无可发布机会”，不必为了凑区间制造伪精度。

## 7. PRICE STRUCTURE
按`price-structure` Skill执行，只回答当前时机，不参与内在价值计算。只对已经完成公司研究与估值解析的对象参与最终机会判断。

## 8. COMPLETION GATE
Gate前必须从`coverage_ledger`机械派生：
- 31/134/346 exact match；
- 所有节点`accounted_for=true`；
- `missing_level1/2/3`为空且必须是真实taxonomy code列表；
- 所有deep节点均已完成盈利链resolution；
- 无未解决`must_split/continue_split`；
- 重点链在有可比主板公司时已完成多公司比较；
- 每条重点链`opportunity_resolution_complete=true`；
- 任何进入【当前机会】的公司必须有完整估值桥和价格结构判断。

`diagnostics.coverage`至少记录：taxonomy、expected_counts、accounted_for_counts、missing_level1/2/3、deep_nodes_total、deep_nodes_resolved、unresolved_must_split_chains、completion_gate_passed。

Gate失败：状态=`incomplete_research`，不生成新的【当前机会】，不得用不完整结果覆盖上一份有效完整状态。

## 持久化边界
Prompt研究只写`data/research/v2/research_state.json`。`coverage_ledger`、市场发现、盈利链、公司比较、估值、价格结构和机会都在同一个state中；不得建立独立中间研究文件或跨期池。Git历史仅用于审计。

## 展示与Shadow
固定章节和公司列读取当前Manifest。当前机会允许为空。估值`review_required`时合理价格和安全价格显示`待复核`。production gate未开启时使用Manifest当前label。
