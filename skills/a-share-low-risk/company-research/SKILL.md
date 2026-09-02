# 公司盈利研究 Skill

## 目的
把本期所有**通过公司准入 Gate 的盈利链**映射到真正受益的主板公司，并用“先便宜淘汰、后昂贵估值”的漏斗压缩工作量：

`Company Mapping Gate → 全链公司召回 → stock_code去重 → 批量财务硬筛 → Driver/盈利质量 Gate → 同类公司去冗余 → 快速估值 Precheck → 剩余公司横向比较 → valuation_set → 完整估值`

核心原则：
- 不得靠 Top-N、每行业配额、龙头名单或代表股截断研究；
- 可以删除**有明确证据证明不值得继续研究**的公司；
- 同一公司级财务/估值输入只获取一次，链维度只保留 `source_chain_ids` 与各链 Driver 匹配结果；
- 不新增独立公司池、估值缓存或候选 JSON；
- 不读取上一期公司、估值、买点或Near-miss名单作为召回起点。

## 输入
1. 本期Prompt全市场景气发现及taxonomy映射；
2. 本期三级行业盈利状态；
3. 所有 admitted profit chains：`trend=improving` 或 `trend=stable AND breadth=divergent`；
4. `data/research/company_industry_index.json`；
5. 本轮实时获取的公司财报、公告、交易所披露、业绩预告/快报、订单/产销/价格/成本、估值等公开证据。

## 1. Company Mapping Gate
公司召回前检查行业映射完整性。

- 已退市、吸收合并、当前无有效交易或其他不可作为交易标的的公司：`skip/inactive`，不影响Completion Gate；
- 明确不属于本轮 admitted Level-3 / profit chain 的 missing/unmapped：记录后继续；
- 可能属于本轮范围：补查行业归属；
- 当前有效交易、属于本轮范围且补查后仍无法解析：`unresolved_in_scope_mapping`，Completion Gate失败。

## 2. 全链召回后按 stock_code 去重
每条 admitted profit chain 必须完整召回全部当前有效、已映射主板公司，禁止在召回阶段做Top-N或先验龙头截断。

召回完成后：
- `company_chain_relations` 保存完整“盈利链 × 公司”关系；
- `unique_companies` 按 `stock_code` 去重；
- 同一公司的财报、扣非、现金流、PE/PB/ROE、日K等公司级输入只获取和判断一次；
- 对不同 `source_chain_ids` 分别判断公司是否真正匹配对应 Driver；
- 去重只减少重复工作，不能删除任何盈利链覆盖证明。

## 3. 批量财务硬筛
对 `unique_companies` 先执行低成本硬筛，至少检查：
- 扣非归母净利润或等价核心盈利是否改善；
- 核心盈利是否为正且方向清楚；
- 营收是否发生与盈利逻辑冲突的明显恶化；
- 经营现金流/盈利质量是否明显失真；
- 一次性损益是否主导归母利润；
- 是否存在重大重组、业务口径突变或不可比变化。

允许排除：
`core_earnings_not_improving / nonrecurring_earnings_dominant / earnings_quality_mismatch / major_business_change / data_unavailable`。

扣非/核心盈利缺失不得默认通过；必须补查公开证据。非经常性损益占归母净利润达到30%及以上时，估值盈利桥只能使用扣非/核心盈利；若核心盈利不改善则排除。

## 4. Driver / 盈利质量 Gate
财务硬筛通过后必须同时满足：
1. 公司级 Driver 明确；
2. 扣非/核心盈利改善；
3. 现金流/盈利质量合格；
4. 持续性足够。

银行、保险等特殊商业模型使用其适用的资产负债表、资本质量和核心盈利指标。

`stable + divergent` 链必须额外证明公司级 Driver/核心盈利真实改善或显著优于同链公司；不能只凭行业 breadth 继续。

## 5. 同类公司去冗余
只在**同一盈利 Driver + 高度相似业务模式/盈利机制**的公司之间判断。

只有当某公司不存在明确独立优势，并在业务纯度、Driver敏感度、核心盈利兑现、现金流/盈利质量、成本/毛利优势、持续性、资本效率、估值优势等多个重要维度被直接可比公司整体压制时，才允许 `dominated_by_peer`。

只要存在明显权衡，例如“一家盈利更强但更贵、另一家盈利稍弱但明显更便宜”，两家都必须保留。禁止每行业固定留1/2/3家或只留龙头。

## 6. 快速估值 Precheck
对剩余公司先读取：
- 当前/TTM PE；
- 动态PE；
- PB、ROE；
- 核心盈利增速；
- 三级同行PE/PB中枢；
- 必要时180日价格位置作为sanity。

只有相对估值**明显极端偏高**，且核心盈利增速、ROE、盈利质量或持续性不足以解释溢价时，才可 `exclude:obviously_expensive`。

禁止跨行业统一绝对PE上限。存在明显权衡或无法确定时必须继续完整估值。Precheck不能直接生成合理价或买点。

## 7. 剩余公司横向比较
所有通过前述过滤的公司都进入横向比较，不设Top-N或固定配额。

比较至少包括：
`业务纯度 / Driver敏感度 / 盈利兑现 / 扣非质量 / 现金流 / 毛利率与成本优势 / 订单或产能可见度 / 持续性 / 资本强度 / 重大口径风险 / 相对估值 / 可估值性`。

## 8. valuation_set
过滤完成后：
- 按股票代码去重进入 `valuation_set`；
- 保留全部 `source_chain_ids`；
- 同一股票只执行一次完整估值、一次价格结构判断和一次买点评估；
- 所有进入 `valuation_set` 的公司必须逐只完整估值，不得因数量多而跳过。

## 9. 守恒诊断
每轮必须机械回答：
- admitted chain count；
- company_chain_relations 数；
- unique_company_count；
- inactive skipped 数；
- unresolved in-scope mappings；
- 财务硬筛通过/排除数；
- Driver/盈利质量 Gate 通过/排除数；
- `dominated_by_peer` 排除数；
- `obviously_expensive` 排除数；
- 深度横向比较数；
- 去重后 valuation_set 数。

只要存在未完成召回的 admitted chain、未完成过滤决策的有效公司或 unresolved in-scope mapping，Completion Gate失败。

## 10. 持久化
公司研究的所有运行结果均为**当前轮临时状态**：公司集合、盈利链关系、硬筛结果、去冗余结果、valuation_set、估值、左侧价值买点、左侧拐点买点和Near-miss都不跨轮持久化。

`research_state.json` 被禁止，不得创建、恢复或读取。跨轮基本面研究记忆只有 `data/research/industry_state.json`。
