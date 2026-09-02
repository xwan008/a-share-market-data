# A股低风险研究编排 Skill

## 目标
执行唯一正式主链：

`DATA GATE → Prompt全市场轻召回 → taxonomy映射 → 三级行业盈利状态读取/刷新 → 公司准入Gate → 盈利链解析 → Company Mapping Gate → 全链公司召回 → stock_code去重 → 财务硬筛 → Driver/盈利质量 Gate → 同类公司去冗余 → 快速估值 Precheck → 横向比较 → 完整估值 → 独立价格结构 → 买点交集 → 接近买点榜 → Completion Gate → 正式发布`

核心原则：**发现阶段广而轻，验证阶段窄而深；三级行业状态跨期复用；公司层先便宜淘汰、后昂贵估值；价值与时机独立；任何硬门失败都 fail closed。**

本 Skill 只服从 `config/research_runtime_policy.json` 和 `config/research_pipeline_manifest.json` 的正式生产契约，不使用数字 schema、shadow、V2/V3 等版本标签作为运行条件。

### 当前轮隔离原则（强制）
除 `data/research/industry_state.json` 的三级行业盈利基线外，上一轮公司、盈利链、估值、价格结构判断、当前买点、Near-miss、榜单结果都不是下一轮输入。

禁止读取、恢复、续跑或发布任何上一轮正式研究结果。`research_state.json` 不存在，也不得重新创建。每次执行必须重新生成本轮公司集合、估值集合、买点评估和最终榜单。

## 1. DATA GATE
正式研究开始前确定最近一个已经完成的A股交易日，读取 `data/health.json` 并验证：
- `health.trade_date` 等于预期交易日；
- `market_status=closed`；
- 数据源 errors 为空；
- 行情覆盖没有实质退化；
- 历史数据覆盖该交易日；
- `full_market_price_structure.json` 的参考交易日与之相同。

### 历史窗口语义（强制）
历史数据存在三个不同用途的窗口，禁止混为一谈：
- **65日 = 轻量摘要窗口**：只用于 `trend_summary` / health 中的5/20/60日摘要、市场宽度和辅助结构描述；
- **120日 = 正式价格结构最低门槛**：低于120个有效交易日时正式价格结构才可判定为历史不足；
- **180日 = 底层滚动历史存储窗口，同时也是正式价格结构与估值 sanity 的目标窗口**。

权威底层历史来源始终是 `data/history_shards/*.json`。正式价格结构直接读取该底层历史，不读取65日摘要作为历史长度判断依据。

兼容旧版 health 时必须遵守：若 `health.schema_version <= 6`，其中 `history.window_days=65` 与 `history.coverage.max_points=65` **都只表示摘要视图长度**，绝不能据此判断底层历史只有65日，也不能据此让 Data Gate / Completion Gate 失败。历史是否满足120/180日要求，必须读取 `history_shards`，或使用新版 health 中明确的 `storage_coverage`。

任一真正的 Data Gate 失败：输出 `data_stale_or_incomplete`，不得发布新的正式买点，也不得修改 `industry_state.json`。

## 2. Prompt全市场轻召回
每次运行都基于当前公开证据，从全市场重新做轻量开放式召回。不能把上一期景气方向、公司、估值、Near-miss 或关注名单当成搜索边界。

必须覆盖资源能源、化工材料、制造设备、科技、消费、医药、金融地产、公用事业/交通运输、农业等主要经济领域；禁止Top-N截断。

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
1. `trend=improving` → `chain_type=improving`；
2. `trend=stable AND breadth=divergent` → `chain_type=stable_divergent`。

`deteriorating`、`unconfirmed`、`stable + 非divergent`不进入公司机会研究。

每条盈利链必须明确：`chain_type / admission_basis / source_level3_codes / profit_driver / leading_variables / profit_transmission / beneficiary_scope / falsifiers`。没有确认 Driver 和利润传导不得仅凭概念相关进入公司层。

## 5. Company Mapping Gate
读取 `data/research/company_industry_index.json`。

- 查询到已退市、吸收合并、当前无有效交易或其他不可作为交易标的的公司：直接 `skip/inactive`，不影响 Completion Gate；
- 非本轮盈利链的 missing/unmapped 只记录；
- 当前有效交易、可能属于本轮 admitted chain 的缺失映射必须补查；
- 补查后仍 unresolved in-scope 才判定 `incomplete_research`。

## 6. 公司层过滤漏斗
### 6.1 全链召回 + stock_code 去重
每条 admitted profit chain 先完整召回全部当前有效主板公司，不得先选龙头、按市值或Top-N截断。

完成召回后，立刻按 `stock_code` 建立唯一公司全集：
- 保留全部 `company_chain_relations` / `source_chain_ids`；
- 公司财报、扣非、现金流、PE/PB/ROE、日K等公司级输入只获取一次；
- 各盈利链只分别判断 Driver 匹配关系。

### 6.2 批量财务硬筛
先用便宜数据排除明显不合格公司：扣非/核心盈利不改善、盈利质量明显失真、一次性收益主导且核心盈利不改善、重大业务变化、关键数据补查后仍不可得等。

### 6.3 Driver / 盈利质量 Gate
财务硬筛通过后必须同时满足：
- 公司级 Driver 明确；
- 扣非/核心盈利改善；
- 现金流/盈利质量合格；
- 持续性足够。

银行、保险等特殊商业模型使用其适用的资产负债表、资本质量和核心盈利指标替代普通经营现金流判断。

### 6.4 同类公司去冗余
只在“同一 Driver + 高度相似业务/盈利机制”的可比公司之间判断。

只有当某公司相对直接可比公司**没有明确独立优势且在多个关键维度被整体压制**时，才允许 `exclude:dominated_by_peer`。比较维度包括业务纯度、Driver敏感度、核心盈利兑现、现金流/盈利质量、成本/毛利优势、持续性、资本效率和估值优势。

只要存在明显权衡，例如“一家盈利更强但更贵、另一家盈利稍弱但明显更便宜”，两家都必须保留。禁止每行业固定留1/2/3家或只留龙头。

### 6.5 快速估值 Precheck
对剩余公司先读取当前/TTM PE、动态PE、PB、ROE、核心盈利增速、三级同行PE/PB中枢；180日价格位置只做sanity。

只有当相对估值**明显极端偏高**，且核心盈利增速、ROE、盈利质量和持续性不足以解释溢价时，才可 `exclude:obviously_expensive`，从而避免无意义的完整估值。

禁止跨行业统一绝对PE上限。高PE必须结合同行估值与核心盈利增长判断；存在明显权衡或无法确定时必须继续完整估值。Precheck只能做明显否定，不能直接生成合理价或买点。

### 6.6 横向比较
只有通过前述过滤的公司进入深度横向比较。所有剩余公司都比较，不设Top-N或固定配额。

比较至少包括：业务纯度、Driver敏感度、盈利兑现、扣非/现金流、毛利率与成本优势、订单/产能可见度、持续性、资本强度、重大口径风险、相对估值、可估值性。

## 7. valuation_set 与完整估值
过滤完成后按 `stock_code` 去重进入 `valuation_set`，保留全部 `source_chain_ids`。同一股票只完整估值一次，结果回填所有相关盈利链。

正常盈利公司固定走：

`核心盈利 → Forward核心EPS → 当前/TTM PE + 动态PE → 三级同行PE → 核心盈利增速调整 → PB/ROE交叉验证 → 180日市场sanity → fair PE区间 → reasonable price → base fair value → 一次MOS → safe_price_ceiling`

只有Manifest规定的异常触发条件才进入 PB-ROE / Residual Income / EV/EBITDA / NAV/DCF / FCF/DCF 等Exception Path。MOS只应用一次。

## 8. 价格结构与买点
价格结构独立于估值。对每家完整非review估值公司读取：`structure_type / structure_entry_range / structure_invalidation / key_level / relative_strength / volume_confirmation / chase_risk / timing_action`。

买点规则：
- `value_eligible = current_price <= safe_price_ceiling`；
- `timing_eligible`来自独立价格结构；
- `buy_price_range = structure_entry_range ∩ (-∞, safe_price_ceiling]`。

只有价值合格、结构合格、交集非空且当前价位于可执行区间，才允许 `buyable_now`。`damaged / overheated`永远不能成为当前低风险买点。

## 9. 接近买点榜
正式买点只允许 `buyable_now`。只要存在可评估非review公司，即使当前买点为0，也输出Top10 Near-miss；Near-miss只当期展示，不形成跨期候选池。

## 10. COMPLETION GATE
正式发布前必须确认：
- Data Gate通过；
- Prompt全市场召回完整；
- taxonomy映射与所需三级状态刷新完成；
- 所有 admitted chains 完成Driver/利润传导解析；
- Company Mapping Gate通过；
- 所有 admitted chains 完整召回公司；
- stock_code 去重完成且保留全部链关系；
- 所有唯一公司完成财务硬筛决策；
- 所有财务筛选 survivor 完成Driver/盈利质量判断；
- 所有继续研究公司完成同类去冗余判断；
- 所有继续研究公司完成快速估值Precheck；
- 所有Precheck survivor完成横向比较；
- valuation_set逐只完成估值或明确review；
- 所有非review公司完成价格结构、买点评估和Near-miss距离；
- 【当前买点】只来自 `buyable_now`。

任一失败：`status=incomplete_research`，不发布本轮正式买点，也不得修改 `industry_state.json`。不存在“回退并发布上一轮榜单”的路径。

## 11. 持久化边界
只允许：
- `data/research/industry_state.json`：三级行业跨期盈利状态，是唯一跨轮研究记忆；
- `data/research/full_market_price_structure.json`：全市场机械价格结构，不属于研究结果状态。

本轮公司集合、盈利链关系、去冗余结果、valuation_set、估值、价格结构判断、买点评估、Near-miss 和最终榜单均为**当轮临时结果**，发布完成即结束，不写入跨轮研究状态文件。

明确禁止：`data/research/research_state.json`、独立候选池、机会池、去冗余名单、周榜缓存、Near-miss池和单独估值缓存。

## 12. 正式输出
固定输出：
`【执行状态】 / 【全市场景气发现】 / 【三级行业盈利状态】 / 【产业链与公司轻筛】 / 【估值与安全价】 / 【价格结构与时机】 / 【当前买点】 / 【接近买点榜】 / 【诊断与失效条件】`。
