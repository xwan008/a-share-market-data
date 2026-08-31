# A股低风险研究 V2 编排 Skill

## 目标
执行一条简单、可审计的研究链：
`数据健康 → 固定Coverage → 全市场景气发现 → 盈利链递归拆解 → 链内公司比较与盈利验证 → 分类估值 → 价格结构 → Completion Gate → 当前机会`

18:00每次从当前全市场重新开始，不从上一期行业、公司或机会名单开始，也不建立周度池、候选池或跨期机会缓存。上一份有效state只用于06:00增量复核和防止不完整新结果覆盖有效旧结果。

## 数据与证据边界
Manifest `authoritative_data`只定义**仓库中允许长期读取的机械数据**，不是全部研究信息来源。

18:00开放式研究必须主动使用当前公开证据补足基本面：公司财报/公告、交易所披露、官方统计、行业协会/产业数据、产品价格与价差、订单/出货/产销、库存/开工/产能利用率，以及必要的可信新闻/研究资料。

公开证据用于本次研究判断，但不得被整理成新的跨期候选池、周度机会池或重复研究缓存。

## Coverage完整性
申万2021固定Coverage只回答有没有漏扫：31个一级、134个二级、346个三级全部`accounted_for`，缺失为0。弱/稳定节点可浅扫描；改善、恶化或显著分化节点必须深研。Coverage不是景气答案池，也不是盈利链终点。

## 固定研究顺序
### 0. DATA HEALTH
确认主板范围、最近完整交易日、最新行情、历史数据和全市场价格结构足够新鲜；同时确认可以访问本次所需公开基本面证据。机械行情数据陈旧时fail closed；公开证据不足则对应节点标记证据不足，不得把“没研究到”解释成“没有机会”。

### 1. FIXED TAXONOMY COVERAGE
在任何重点行业判断前完成31/134/346防漏检查。分类表只防漏，不预先决定景气。

### 2. OPEN MARKET PROFITABILITY DISCOVERY
在完整Coverage上横向比较当前公开基本面证据，至少关注收入/利润、毛利率/利润率、产品价格/价差、订单/出货/销量/产量、库存/开工/产能利用率、出口/资本开支和行业特有领先变量。

首先回答哪些行业变好、恶化或分化，幅度和速度如何，未来1–2季度为什么可能继续。禁止从熟悉股票、上一期机会或当前对话曾出现的行业开始倒推。

### 3. PROFIT CHAIN DECOMPOSITION
对改善、恶化或显著分化节点继续拆，直到同链公司基本共享：1）直接盈利Driver；2）领先变量；3）利润传导机制与可比业务暴露。任一不满足继续按产品/服务、工艺路线、应用场景、客户需求、原料成本、供需/价格/价差等拆分。继续拆只剩公司名称分组时停止。

任何`must_split/continue_split`必须在本次结束前拆完，或因公开证据不足明确降级`unconfirmed`并说明缺口。

### 4. CHAIN COMPANY COMPARISON + COMPANY RESEARCH
只从本期确认的盈利链出发识别主板受益公司，再按`company-research` Skill验证。重点链有多个直接受益公司时必须横向比较；没有低风险位置时`current_opportunity_best`可为空。

不建立跨期公司召回池或反向补池机制；补漏依赖固定Coverage和高质量盈利链拆分。

### 5. VALUATION
按`valuation` Skill执行。当前价格只是比较基准，不能反向修改合理价格；合理价格与安全价格必须来自同一盈利基础。

### 6. PRICE STRUCTURE
按`price-structure` Skill执行，只回答当前时机，不参与内在价值计算。

### 7. COMPLETION GATE + OPPORTUNITY SYNTHESIS
生成【当前机会】前必须满足：31/134/346全部accounted_for；无缺失节点；无未解决must_split；强改善/显著分化节点完成盈利链研究；重点链有充分主板可比对象时完成多公司比较。

`diagnostics.coverage`至少记录taxonomy、expected_counts、accounted_for_counts、missing_level1/2/3、unresolved_must_split_chains、completion_gate_passed。

Gate失败：状态=`incomplete_research`，不生成新的【当前机会】，不得用不完整结果覆盖上一份有效完整状态。

## 持久化边界
Prompt研究只写`data/research/v2/research_state.json`。本次行业状态、盈利链、公司比较、估值、机会都作为state组成部分，不建立独立中间研究文件或跨期池。机械数据只读Manifest `authoritative_data`；公开证据按本次研究实时获取；Git历史仅用于审计。

## 展示与Shadow
固定章节和公司列读取当前Manifest。当前机会允许为空。估值`review_required`时合理价格和安全价格显示`待复核`。production gate未开启时使用Manifest当前label。
