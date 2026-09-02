# A股低风险研究编排 Skill

## 目标
执行唯一正式主链：

`DATA GATE → Prompt全市场轻召回 → taxonomy映射 → 三级行业盈利状态读取/刷新 → 公司准入Gate → 盈利链解析 → Company Mapping Gate → 全链公司召回 → stock_code去重 → 财务硬筛 → Driver/盈利质量 Gate → 同类公司去冗余 → 快速估值 Precheck → 横向比较 → 完整估值 → reasonable_buy_range → 独立价格结构 → 左侧价值买点榜 → 左侧拐点买点榜 → 接近买点榜 → Completion Gate → 正式发布`

核心原则：**发现阶段广而轻，验证阶段窄而深；三级行业状态跨期复用；公司层先便宜淘汰、后昂贵估值；价值决定 WHERE，结构只决定是否出现左侧 TURN；任何硬门失败都 fail closed。**

本 Skill 只服从 `config/research_runtime_policy.json` 和 `config/research_pipeline_manifest.json` 的正式生产契约。

### 当前轮隔离原则（强制）
除 `data/research/industry_state.json` 的三级行业盈利基线外，上一轮公司、盈利链、估值、价格结构判断、买点、Near-miss、榜单结果都不是下一轮输入。

`research_state.json` 不存在，也不得重新创建。每次执行必须重新生成本轮公司集合、估值集合、合理买入区、两类买点和最终榜单。

## 1. DATA GATE
正式研究开始前确定最近一个已经完成的A股交易日，读取 `data/health.json` 并验证：
- `health.trade_date` 等于预期交易日；
- `market_status=closed`；
- 数据源 errors 为空；
- 行情覆盖没有实质退化；
- 历史数据覆盖该交易日；
- `full_market_price_structure.json` 的参考交易日与之相同。

### 历史窗口语义（强制）
- **65日**：轻量摘要窗口；
- **120日**：正式价格结构最低门槛；
- **180日**：底层滚动历史存储窗口，也是正式结构与估值sanity目标窗口。

权威底层历史来源始终是 `data/history_shards/*.json`。禁止把65日摘要误判成底层只有65日历史。

真正Data Gate失败：输出 `data_stale_or_incomplete`，不得发布新的正式买点，也不得修改 `industry_state.json`。

## 2. Prompt全市场轻召回
每次运行都基于当前公开证据，从全市场重新做轻量开放式召回。不能把上一期景气方向、公司、估值、Near-miss或关注名单当搜索边界。

必须覆盖：资源能源、化工材料、制造设备、科技、消费、医药、金融地产、公用事业/交通运输、农业；禁止Top-N截断。

优先证据：行业收入利润/利润率、产品价格与价差、库存、开工率/产能利用率、订单/出货/销量/产量、进出口/供需、代表性公司经营数据及真正改变供需或成本的政策。板块涨幅和ETF强弱只能辅助。

## 3. taxonomy映射与三级盈利状态
景气方向映射到申万2021 taxonomy；映射到一级/二级后继续展开到所有与本轮盈利逻辑相关的三级行业。

三级状态规则：
1. 已有有效状态直接复用；只有新证据、失效信号或实质变化才做日度深度刷新；
2. 从未有状态的节点只初始化该节点；
3. 过期/无效只重验该节点；
4. 周五18:00对本轮发现方向映射出的相关三级行业全量重验，失败则下一个可用工作日18:00补做。

不存在首次全库Bootstrap或单节点缺失触发全库重建。

## 4. 公司准入 Gate 与盈利链
三级行业进入公司层仅有：
- `trend=improving` → `chain_type=improving`；
- `trend=stable AND breadth=divergent` → `chain_type=stable_divergent`。

`deteriorating`、`unconfirmed`、普通stable不进入公司机会研究。

每条盈利链必须明确：
`chain_type / admission_basis / source_level3_codes / profit_driver / leading_variables / profit_transmission / beneficiary_scope / falsifiers`。

## 5. Company Mapping Gate
读取 `data/research/company_industry_index.json`。

- inactive/untradable：`skip/inactive`；
- 非本轮盈利链的missing/unmapped只记录；
- 可能属于本轮范围的缺失映射必须补查；
- 补查后仍 unresolved in-scope → `incomplete_research`。

## 6. 公司层过滤漏斗
### 6.1 全链召回 + stock_code 去重
每条 admitted profit chain 完整召回全部当前有效主板公司，不得先选龙头或Top-N。

保留全部 `company_chain_relations / source_chain_ids`，公司级财务、估值和历史输入按stock_code只获取一次。

### 6.2 批量财务硬筛
排除：扣非/核心盈利不改善、盈利质量失真、一次性收益主导且核心盈利不改善、重大业务变化、关键数据补查后仍不可得等。

### 6.3 Driver / 盈利质量 Gate
必须同时满足：
- 公司级Driver明确；
- 扣非/核心盈利改善；
- 现金流/盈利质量合格；
- 持续性足够。

### 6.4 同类公司去冗余
只允许在“同一Driver + 高度相似业务/盈利机制”内排除被直接可比公司多维度整体压制、且没有独立优势的公司。

存在明显权衡必须同时保留；禁止每行业固定留1/2/3家或只留龙头。

### 6.5 快速估值 Precheck
读取当前/TTM PE、动态PE、PB、ROE、核心盈利增速、三级同行PE/PB中枢。

只有相对估值明显极端且增长/ROE/质量/持续性不能解释时，才 `exclude:obviously_expensive`。禁止跨行业统一PE上限。

### 6.6 横向比较
所有survivor都比较，不设Top-N或固定配额。

## 7. valuation_set 与完整估值
按 `stock_code` 去重进入 `valuation_set`；所有公司必须完整估值或明确review。

正常盈利公司固定走：

`核心盈利 → Forward核心EPS → 当前/TTM PE + 动态PE → 三级同行PE → 核心盈利增速调整 → PB/ROE交叉验证 → 周期/口径检查 → 180日市场sanity → fair PE区间 → reasonable_price_range → base_fair_value → 一次MOS → safe_price_ceiling → reasonable_buy_range`

必须区分：
- `reasonable_price_range`：合理价值区；
- `safe_price_ceiling`：安全价上限，不等于买入区；
- `reasonable_buy_range`：本榜单真正使用的合理买入区。

`reasonable_buy_range`必须由估值独立产生、有上下界、上沿不高于safe price ceiling，且不能参考技术结构。

强周期公司禁止机械外推景气高点盈利；必要时使用正常化盈利或触发Exception Path。

## 8. 独立价格结构
对每家完整非review估值公司读取：
`structure_type / structure_entry_range / structure_invalidation / key_level / relative_strength / volume_confirmation / chase_risk / timing_action / left_turn_confirmed / left_turn_basis`。

价格结构不能修改 `reasonable_buy_range`，也不是左侧价值榜的硬门。

## 9. 两个正式买点榜
### 9.1 左侧价值买点榜
核心条件：

`left_value_buyable_now = current_price ∈ reasonable_buy_range`

只要基本面、估值仍有效且当前价格进入合理买入区，即可进入**左侧价值买点榜**。当前仍在下跌、transition甚至技术damaged，不得仅因技术结构未确认而把它从左侧价值榜淘汰；必须清楚展示结构风险和失效条件。

### 9.2 左侧拐点买点榜
核心条件：

`left_turn_buyable_now = left_value_buyable_now AND left_turn_confirmed`

因此必须满足：

`左侧拐点买点榜 ⊂ 左侧价值买点榜`

左侧拐点要求价格仍在合理买入区内，并出现从左侧下跌/筑底向上转折的确认，例如：停止连续创新低、HL、关键支撑承接、重新站回关键位/均线、小级别突破配合量价确认等。

单纯既有右侧 `trend_continuation` 不等于左侧拐点；已经离开合理买入区的强势股也不能进入拐点榜。

`damaged / overheated / unavailable` 不能判为 `left_turn_confirmed=true`，但其中的技术damaged不自动取消左侧价值榜资格。

### 9.3 禁止单一 buyable_now 语义
不再使用“价值 × 结构交集才是唯一买点”的旧逻辑，也不再发布单一 `buyable_now` 榜。

正式买点只能来自：
- `left_value_buyable_now`；
- `left_turn_buyable_now`。

## 10. 接近买点榜
Near-miss只收**尚未进入 `reasonable_buy_range`**、但距离合理买入区已经较近的非review公司。

默认Top10，仅用于展示，不形成跨期候选池。

距离核心锚改为合理买入区：
- 当前价高于买入区上沿：计算到上沿的 `value_gap_pct`；
- 已进入合理买入区：必须进入左侧价值榜，不再作为Near-miss；
- 技术结构不是Near-miss的硬距离门槛，可作为“下一触发点”辅助展示。

## 11. COMPLETION GATE
正式发布前必须确认：
- Data Gate通过；
- Prompt全市场召回完整且无Top-N截断；
- taxonomy映射与所需三级状态刷新完成；
- 所有 admitted chains 完成Driver/利润传导解析；
- Company Mapping Gate通过；
- 所有 admitted chains 完整召回公司；
- stock_code去重且保留全部链关系；
- 所有唯一公司完成财务硬筛；
- survivor完成Driver/盈利质量、去冗余、Precheck、横向比较；
- valuation_set逐只完成估值或明确review；
- 所有非review公司产生 `reasonable_buy_range`；
- 所有非review公司完成价格结构和 `left_turn_confirmed` 判断；
- 所有非review公司完成左侧价值买点评估；
- 左侧拐点榜逐只验证为左侧价值榜子集；
- Near-miss仅来自尚未进入reasonable_buy_range的公司。

任一失败：`status=incomplete_research`，不发布本轮正式买点，也不得修改 `industry_state.json`。不存在回退发布上一轮榜单的路径。

## 12. 持久化边界
只允许：
- `data/research/industry_state.json`：唯一跨轮基本面研究记忆；
- `data/research/full_market_price_structure.json`：全市场机械价格结构。

本轮公司集合、盈利链、去冗余结果、valuation_set、估值、reasonable_buy_range、两类买点、Near-miss和最终榜单全部为当轮临时结果。

明确禁止：`data/research/research_state.json`、独立候选池、机会池、周榜缓存、Near-miss池和单独估值缓存。

## 13. 正式输出
固定输出：
`【执行状态】 / 【全市场景气发现】 / 【三级行业盈利状态】 / 【产业链与公司轻筛】 / 【估值与合理买入区】 / 【价格结构与拐点】 / 【左侧价值买点榜】 / 【左侧拐点买点榜】 / 【接近买点榜】 / 【诊断与失效条件】`。
