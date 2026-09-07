# A股低风险研究编排 Skill

## 目标
执行唯一正式主链：

`DATA GATE → 全市场/全行业召回 → taxonomy映射 → 三级行业盈利状态 → 公司全集扫描 → 绝对股价硬门 → Gate1 → Gate2 → Gate3同类择优 → Gate4 → 完整估值 → reasonable_buy_range + low_risk_buy_range → 独立价格结构 → 左侧价值买点榜 → 左侧拐点买点榜 → Near-miss → Completion Gate → 正式发布`

核心原则：**发现阶段广而轻，验证阶段窄而深；公司层先便宜淘汰、后昂贵研究；合理价值、合理买入、低风险执行三层价值语义必须分开；价值决定 WHERE，结构只决定 TURN；任何硬门失败都 fail closed。**

本 Skill 服从 `config/research_runtime_policy.json`、`config/research_pipeline_manifest.json` 与 `valuation/SKILL.md`、`price-structure/SKILL.md`。若旧契约仍把 `reasonable_buy_range` 定义成 MOS 后5%窄带，以新版估值 Skill 的“双买入区”语义为准，旧窄带语义迁移到 `low_risk_buy_range`。

### 当前轮隔离原则（强制）
除 `data/research/industry_state.json` 的三级行业盈利基线外，上一轮公司、盈利链、估值、价格结构判断、买点、Near-miss、榜单结果都不是下一轮输入。

`research_state.json` 不存在，也不得重新创建。每次执行必须重新生成本轮公司集合、估值集合、合理买入区、低风险买入区、两类买点和最终榜单。

## 1. DATA GATE
正式研究开始前确定最近一个已经完成的A股交易日，读取 `data/health.json` 并验证：
- `health.trade_date` 等于预期交易日；
- `market_status=closed`；
- 数据源 errors 为空；
- 行情/财务/估值覆盖没有实质退化；
- 历史数据覆盖该交易日；
- `full_market_price_structure.json` 的参考交易日与之相同。

历史窗口：65日仅为轻量摘要；120日为正式价格结构最低门槛；180日为底层滚动历史和正式结构/估值sanity目标窗口。权威底层历史来源始终是 `data/history_shards/*.json`。

真正Data Gate失败：输出 `data_stale_or_incomplete`，不得发布新的正式买点，也不得修改 `industry_state.json`。

## 2. 全市场/全行业召回
每次运行都从当前全市场重新开始，不能把上一期景气方向、公司、估值、Near-miss或关注名单当搜索边界。

必须覆盖完整申万2021一级行业。逐行业检查领先变量/第一锚、最新盈利兑现、反向证据，并给出 `improving / neutral / deteriorating / uncertain`。资源能源必须看商品价格/价差/供需/库存；制造、科技、消费、医药等使用订单、出货、价格、库存、利用率、资本开支、招投标和需求等适配变量。

只有 `improving` 一级行业继续下钻到真正贡献盈利改善的细分产业链并映射申万三级。三级准入仅允许：
- `trend=improving`；
- 或 `trend=stable AND breadth=divergent`。

## 3. Shard全集与公司准入
正式 shard 扫描只允许唯一读取路径：**锁 SHA → clone/下载 → 本地读**。

1. 锁定本轮生产仓库最新 `main` commit SHA 为 `repo_commit_sha`；规则文件、运行时数据和 shard 正文不得混用不同 SHA。
2. 锁定后必须先把 `repo_commit_sha` 对应的仓库 clone、checkout 或下载归档到当前本地运行环境。GitHub Connector 不得作为正式 shard 正文扫描通道，也不得与本地读取并列为等价路径。
3. 若使用 clone，必须验证 `HEAD == repo_commit_sha`；若使用归档，必须确认归档明确对应 `repo_commit_sha`。SHA 校验通过后才能开始扫描。
4. 在本地副本中枚举全部 `data/shards/*.json`，记录 `shard_file_count`，并通过本地文件系统/Python 对每个 shard 执行完整 JSON 解析。
5. 只有本地完整解析成功的 shard 才计入 `actual_shard_content_read_count`。目录元数据、Connector 正文、搜索片段、分页/分段内容和截断文本都不能计入正式完成数。
6. GitHub Connector 只允许用于锁定/确认 SHA、读取少量规则或配置、诊断与 spot check；即使单个 shard 能被 Connector 完整返回，也不能代替本地扫描，也不能贡献正式计数。
7. 若 `repo_commit_sha` 无法 clone/下载/checkout 到本地，或本地 SHA 校验失败，立即返回 `local_snapshot_unavailable`；禁止退回 Connector 逐 shard 扫描。
8. 若本地副本已就绪，但存在 shard 缺失、JSON 损坏、解析失败或 `actual_shard_content_read_count != shard_file_count`，返回 `shard_scan_incomplete`；禁止用 Connector 分段读取补齐正式扫描。

记录：`repo_commit_sha / scan_source / shard_file_count / actual_shard_content_read_count / company_universe_count`。Completion Gate前必须满足：
`actual_shard_content_read_count == shard_file_count`。

公司行业映射唯一运行时来源为shard自带 `industry_mapping_status / sw_level3_code / sw_level3_name`：
- missing → `industry_unmapped`；
- mapped但非准入三级 → `industry_not_eligible`；
- 命中准入三级 → `mapped+eligible`，进入绝对股价硬门。

### 绝对股价硬门（Gate1之前，强制）
对全部 `mapped+eligible` 公司，在任何 Gate1 估值风险判断之前先检查当前股价：
- `current_price > 100` → `exclude:price_above_100`，立即终止本轮公司研究，不得进入Gate1、后续估值、两个正式买点榜或Near-miss；
- `current_price <= 100` → 通过绝对股价硬门，进入Gate1。

100元为**含边界上限**：恰好100元允许进入，只有严格大于100元才剔除。该约束是本低风险榜的独立公司准入条件，不因PE/PB较低、相对同行便宜、合理价值更高或技术结构更强而放宽。

禁止Top-N、只挑龙头或因公司数量大而跳过。

## 4. 公司层 Gate
### Gate1｜估值风险过滤
只排除多个维度共同显示明显透支、估值风险极高且增长/ROE/质量无法解释的公司。参考当前/TTM PE、动态PE、PB、ROE、核心盈利增速、同类相对估值和必要历史位置。Gate1不产生正式合理价。

### Gate2｜核心盈利兑现
确认核心/扣非利润方向、主营对产业链真实暴露、收入/利润率/现金流/订单/销量/价格等经营支持，以及一次性事项/非经常损益/业务变化。明显不受益、核心盈利恶化或利润失真可排除；证据冲突时最小必要补查。

### Gate3｜同类横向择优
在Gate2 survivors中按“核心盈利驱动”形成足够宽且可统一排序的可比组，原则上每组只留1家进入Gate4。

统一比较：`earnings_realization / profitability_quality / valuation_attractiveness / business_purity / independent_advantage`。

强周期/资源组必须深比较成本曲线/单位成本/AISC、当前与未来1–3年可验证产量、资源储量/品位/产能质量/项目进度、商品价格敏感度/伴生品/周期下行风险、现金流/负债/估值。必要数据不足则最小公开资料补查；仍无法可靠排序则 `research_uncertain:<reason>`。

Gate3终态：
- `pass:best_in_group`
- `exclude:inferior_to_group_winner:<reason>`
- `research_uncertain:<reason>`

每组至少记录 `group_basis / winner / winner_reason / key_tradeoff / excluded_count`。

### Gate4｜公司级确认
仅对Gate3通过公司确认主营贡献、公司Driver、订单/价格/销量/利用率/利润率/现金流、盈利质量、未来1–2季度持续性及重大反向证据。终态：`pass / exclude:<reason> / research_uncertain`。

## 5. 完整估值与四层价格体系
仅对Gate4=pass执行。先识别：
- `normal_equity`；
- `strong_cycle_or_commodity`。

正常公司固定顺序：
`核心盈利 → Forward核心EPS → 当前/TTM PE + 动态PE → 三级同行 → 增长/质量调整 → PB/ROE交叉验证 → 周期/口径检查 → 180日sanity → fair PE区间 → reasonable_price_range → base_fair_value → reasonable_buy_range → 一次MOS → safe_price_ceiling → low_risk_buy_range`

四层语义必须严格分开：
1. `reasonable_price_range`：合理价值区，大致值多少钱；
2. `reasonable_buy_range`：正常合理买入区，什么价格已经值得左侧参与；
3. `safe_price_ceiling`：base_fair_value应用一次MOS后的高安全边际上限；
4. `low_risk_buy_range`：围绕safe_price_ceiling的低风险/高安全边际窄执行带。

正常路径固定公式：
`reasonable_buy_range.lower = reasonable_price_range.lower`
`reasonable_buy_range.upper = base_fair_value`
`safe_price_ceiling = base_fair_value × (1 - margin_of_safety_pct)`
`low_risk_buy_range.upper = safe_price_ceiling`
`low_risk_buy_range.lower = safe_price_ceiling × 0.95`

`reasonable_buy_range` 不使用MOS；5%仅是 `low_risk_buy_range` 的执行带宽；MOS只应用一次。旧 `safe_price_range` 字段继续废弃，其窄带语义迁移到 `low_risk_buy_range`。

强周期公司必须先获取并评估最直接商品价格/价差、供需、库存和周期位置，形成 `normalized_core_eps`，区分结构性盈利和周期性盈利。高景气利润不得机械外推；周期景气不得通过EPS和PE重复计价。缺少周期第一锚 → `valuation_incomplete:missing_cycle_anchor`。

## 6. 当前价格位置与折价复核
每家公司同时输出：
- `valuation_position = above_reasonable_buy_range / inside_reasonable_buy_range / below_reasonable_buy_range`
- `low_risk_position = above_low_risk_buy_range / inside_low_risk_buy_range / below_low_risk_buy_range`

若 `current_price < reasonable_buy_range.lower`，执行 `discount_sanity_check`：重新检查盈利链、产业领先变量、核心盈利、周期位置、重大事项和估值假设。

若复核仍有效且 `current_price >= low_risk_buy_range.lower`，不得因为价格更低而机械取消价值资格，标记 `deeper_discount`；若当前位于low-risk带，再标记 `low_risk=true`。

只有 `current_price < low_risk_buy_range.lower` 才进入 `deep_discount_review`，完成复核与重新估值前不得进入正式价值榜或Near-miss。

## 7. 独立价格结构
结构只负责 timing/拐点，不得修改 `reasonable_price_range / reasonable_buy_range / low_risk_buy_range`。

对完整非review估值公司读取：
`structure_type / structure_entry_range / structure_invalidation / key_level / relative_strength / volume_confirmation / chase_risk / timing_action / left_turn_confirmed / left_turn_basis`。

## 8. 两个正式买点榜
### 8.1 左侧价值买点榜
`left_value_buyable_now = current_price <= reasonable_buy_range.upper AND valuation_review_valid AND NOT deep_discount_review`

- `inside_reasonable_buy_range`：正常价值机会；
- `below_reasonable_buy_range` 且 `discount_sanity_check` 通过：以 `deeper_discount` 进入；
- `inside_low_risk_buy_range`：在价值资格之上增加 `low_risk=true`；
- 技术结构未确认不得否决价值资格，但必须展示结构风险。

### 8.2 左侧拐点买点榜
`left_turn_buyable_now = left_value_buyable_now AND left_turn_confirmed`

因此 `左侧拐点买点榜 ⊂ 左侧价值买点榜`。结构只负责把已经具备价值资格的公司进一步筛出开始转折的子集。

## 9. Near-miss
Near-miss仅收：
`current_price > reasonable_buy_range.upper`

默认Top10，仅展示，不持久化。`value_gap_pct` 必须以 `reasonable_buy_range.upper` 为唯一价值距离锚。禁止用 `low_risk_buy_range.upper` 或 `safe_price_ceiling` 排Near-miss。

已经 `left_value_buyable_now=true` 或 `deep_discount_review` 的公司不得进入Near-miss。

## 10. COMPLETION GATE
正式发布前必须确认：
- Data Gate通过；
- 一级行业完整扫描且所有improving方向完成三级下钻；
- 所有准入三级正确应用industry_state；
- 所有shards完整读取且计数相等；
- 每只公司都有行业处理终态；
- 所有 `mapped+eligible` 公司都完成绝对股价硬门；`current_price > 100` 必须终止为 `exclude:price_above_100`，只有 `current_price <= 100` 才能进入Gate1；
- Gate1 survivors有Gate2终态；
- Gate2 survivors全部完成Gate3宽分组、统一比较和横向择优；
- Gate3每个真正可比组原则上仅1家pass，其余明确exclude或uncertain；
- Gate3 pass全部进入Gate4并有终态；
- 所有Gate4=pass完成正确估值路由，并分别产生 `reasonable_price_range / base_fair_value / reasonable_buy_range / safe_price_ceiling / low_risk_buy_range / valuation_position / low_risk_position`；
- 必要的 `discount_sanity_check / deep_discount_review` 已处理；
- 所有非review公司完成价格结构和左侧价值判断；
- 左侧拐点榜逐只验证为左侧价值榜子集；
- Near-miss只来自 `above_reasonable_buy_range`，且距离锚是 `reasonable_buy_range.upper`。

任一硬门失败：`status=incomplete_research`，不发布本轮正式买点，也不得用上一轮榜单回退。

## 11. 持久化边界
只允许：
- `data/research/industry_state.json`：唯一跨轮基本面研究记忆；
- `data/research/full_market_price_structure.json`：全市场机械价格结构。

本轮公司集合、Gate结果、估值、`reasonable_buy_range`、`low_risk_buy_range`、两类买点、Near-miss和最终榜单均为当轮临时结果。

明确禁止：`data/research/research_state.json`、独立候选池、机会池、周榜缓存、Near-miss池和单独估值缓存。

## 12. 正式输出
固定输出：
`【执行状态】 / 【全市场景气发现】 / 【三级行业盈利状态】 / 【产业链与公司漏斗】 / 【Gate3同类比较】 / 【估值四层价格】 / 【价格结构与拐点】 / 【左侧价值买点榜】 / 【左侧拐点买点榜】 / 【接近买点榜】 / 【诊断与失效条件】`。

每只正式估值公司至少展示：`current_price / reasonable_price_range / base_fair_value / reasonable_buy_range / low_risk_buy_range / valuation_position / low_risk_position / discount_sanity_check / left_value_buyable_now`。
