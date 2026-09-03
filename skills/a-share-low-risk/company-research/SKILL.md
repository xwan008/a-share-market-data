# 公司盈利研究 Skill

## 目的
把本期所有**通过公司准入 Gate 的盈利链**映射到真正受益的主板公司，并用“先便宜淘汰、后昂贵估值”的漏斗压缩工作量：

`三级准入集合 → 完整扫描 data/shards/*.json → 行业终态 → Gate1 → Gate2 → Gate3 → Gate4/valuation_set → 完整估值`

核心原则：
- 不得靠 Top-N、每行业配额、龙头名单或代表股截断研究；
- 可以删除**有明确证据证明不值得继续研究**的公司；
- 同一公司级财务/估值输入只获取一次，链维度只保留 `source_chain_ids` 与各链 Driver 匹配结果；
- 不新增独立公司池、估值缓存或候选 JSON；
- 不读取上一期公司、估值、买点或 Near-miss 名单作为召回起点；
- 正式运行禁止依赖 `data/research/company_industry_index.json` 构造公司全集或行业映射。

## 输入
1. 本期 Prompt 全市场景气发现及 taxonomy 映射；
2. `data/research/industry_state.json`；
3. 本轮 admitted Level-3 集合：`trend=improving` 或 `trend=stable AND breadth=divergent`；
4. **全部** `data/shards/*.json` 股票记录；
5. 本轮实时获取的公司财报、公告、交易所披露、业绩预告/快报、订单/产销/价格/成本、估值等公开证据。

## 0. 运行时读取协议（强制）
正式执行必须按以下顺序读取，不能因为 GitHub 目录接口只返回文件元数据而误判为 shard 无法完整扫描：

1. 先读取 `data/research/industry_state.json`，结合本轮一级行业扫描与三级映射，形成**当前轮临时 admitted Level-3 集合**；该临时集合只保存三级代码/名称、trend、breadth、driver 等本轮必要字段，不保存公司候选。
2. 再枚举 `data/shards/` 下的全部 `*.json` 文件，记录 `shard_file_count`。
3. 对枚举出的每一个 shard，必须继续读取该文件**正文内容**；目录列表/contents API 返回的 name、path、sha、size 等元数据只用于枚举，不能代替正文扫描。
4. 若执行环境支持本地仓库或工作区，优先在最新 `main` 本地副本中直接遍历 `data/shards/*.json`；若使用 GitHub 连接器，则先枚举文件，再按 `path` 使用文件读取接口逐个读取正文。两种方式在 Completion Gate 语义上等价。
5. 对每条股票记录直接使用 shard 自带的 `industry_mapping_status / sw_level3_code / sw_level3_name` 判断行业终态：
   - 映射缺失 → `industry_unmapped`
   - 已映射但不在 admitted Level-3 集合 → `industry_not_eligible`
   - 已映射且命中 admitted Level-3 集合 → `mapped+eligible`，进入 Gate1
6. `data/research/company_industry_index.json`、历史正式结果、旧候选、旧 Near-miss、搜索结果或聚合摘要均不得代替本步骤构造公司全集。
7. **禁止错误阻断**：仅因为目录 API 不能一次性返回全部 shard 正文、返回被分页/截断、或只显示元数据，不得判定 `shard_scan_incomplete`。只有在实际尝试逐文件读取后，仍存在无法读取的 shard 正文，且不能通过最新 `main` 本地副本完成扫描时，才可认为 shard 内容扫描不完整。
8. Completion Gate 前必须核对：枚举文件数、实际成功读取文件数、处理股票记录数；`actual_shard_content_read_count` 必须等于 `shard_file_count`。

## 1. Company Mapping Gate
公司全集与行业映射的唯一运行时来源是 shard 正文，不再读取 `company_industry_index.json` 构造公司池。

- `industry_mapping_status` 缺失/未映射：`industry_unmapped`；
- 映射到非 admitted Level-3：`industry_not_eligible`；
- 命中 admitted Level-3：`mapped+eligible` 并进入 Gate1；
- 对可能属于本轮范围但 shard 映射异常的记录，允许做最小补查，但不得通过补查结果绕过 shard 全集扫描。

## 2. 全链召回后按 stock_code 去重
所有 `mapped+eligible` 股票记录必须进入公司层，不得在召回阶段做 Top-N 或先验龙头截断。

召回完成后：
- `company_chain_relations` 保存完整“盈利链 × 公司”关系；
- `unique_companies` 按 `stock_code` 去重；
- 同一公司的财报、扣非、现金流、PE/PB/ROE、日K等公司级输入只获取和判断一次；
- 对不同 `source_chain_ids` 分别判断公司是否真正匹配对应 Driver；
- 去重只减少重复工作，不能删除任何盈利链覆盖证明。

## 3. Gate1｜估值风险过滤
Gate1 只排除多个维度共同显示明显透支、估值风险极高且盈利增长、ROE 或公司质量无法解释的公司。

至少参考：当前/TTM PE、动态 PE、PB、ROE、核心盈利增速、同类相对估值和必要历史位置。Gate1 不生成正式合理价。

## 4. Gate2｜公司核心盈利兑现确认
Gate1 通过后至少检查：
- 扣非归母净利润或等价核心盈利是否改善；
- 核心盈利是否为正且方向清楚；
- 主营是否真实暴露于本轮盈利链；
- 收入、利润率、现金流、订单、销量、价格等是否支持；
- 一次性损益是否主导归母利润；
- 是否存在重大重组、业务口径突变或不可比变化。

允许排除：
`core_earnings_not_improving / nonrecurring_earnings_dominant / earnings_quality_mismatch / major_business_change / not_exposed_to_profit_chain / data_unavailable`。

扣非/核心盈利缺失不得默认通过；必须补查公开证据。非经常性损益占归母净利润达到 30% 及以上时，估值盈利桥只能使用扣非/核心盈利；若核心盈利不改善则排除。

## 5. Gate3｜同类公司横向择优
Gate3 只做一件事：在 Gate2 已通过的公司中，找出真正同类的公司，并保留当前综合风险收益比最优的代表继续研究。

先判断是否真正同类：
- 按主营业务和核心盈利驱动分组；
- 不以申万三级名称机械代替真实可比关系；
- 盈利来源、产业链位置或商业模式明显不同的公司，不得强行放在同一组比较。

同类公司统一比较以下 5 个维度：
1. `earnings_realization`：核心/扣非盈利兑现强度与持续性；
2. `profitability_quality`：ROE、利润率、现金流、资产负债与盈利稳定性；
3. `valuation_attractiveness`：当前价格下的估值吸引力；
4. `business_purity`：主营对本轮盈利逻辑的暴露纯度；
5. `independent_advantage`：成本、资源、产能、技术、产品、客户、渠道、结构性成长等可验证竞争优势。

原则上每个真正同类的可比组优先保留当前综合风险收益比最优的代表进入后续研究。

- 不设置全市场固定通过数量；
- 不设置每个申万三级固定名额；
- 通过数量由本轮实际比较结果自然决定；
- 如果两家公司盈利机制明显不同，应拆成不同组后分别比较；
- `independent_advantage` 用于解释竞争力和判断是否应拆组，不是自动放行条件。

对强周期/资源类公司进行同组比较时，必须在上述 5 维中实际考虑成本曲线、资源/产能质量、未来产量增长、商品价格敏感度与周期下行风险，但不新增独立 Gate。

Gate3 终态：
- `pass:best_in_group`
- `exclude:inferior_to_group_winner:<reason>`
- `research_uncertain:<reason>`

所有 Gate3 排除都必须说明相对于同组更优公司的主要差距；公司本身优秀不等于必须保留。

## 6. Gate4 / valuation_set
Gate3 通过公司进入公司级重点确认与后续完整估值。

- 按股票代码去重进入 `valuation_set`；
- 保留全部 `source_chain_ids`；
- 同一股票只执行一次完整估值、一次价格结构判断和一次买点评估；
- 所有进入 `valuation_set` 的公司必须逐只完整估值，不得因数量多而跳过。

## 7. 守恒诊断
每轮必须机械回答：
- `shard_file_count`；
- `actual_shard_content_read_count`；
- `company_universe_count`；
- `industry_mapped_company_count`；
- `industry_unmapped_company_count`；
- `industry_eligible_company_count`；
- `industry_not_eligible_company_count`；
- Gate1 通过/排除数；
- Gate2 通过/排除数；
- Gate3 真实可比组数；
- Gate3 `pass:best_in_group` 数；
- Gate3 `exclude:inferior_to_group_winner` 数；
- Gate3 `research_uncertain` 数；
- 去重后 valuation_set 数。

至少满足：
`actual_shard_content_read_count = shard_file_count`

`company_universe_count = industry_mapped_company_count + industry_unmapped_company_count`

`industry_mapped_company_count = industry_eligible_company_count + industry_not_eligible_company_count`

`Gate3输入公司数 = Gate3 pass数 + Gate3 exclude数 + Gate3 research_uncertain数`

只要存在实际未读取正文的 shard、未完成过滤决策的 eligible 公司或 unresolved in-scope mapping，Completion Gate 失败。

## 8. 持久化
公司研究的所有运行结果均为**当前轮临时状态**：admitted Level-3 临时集合、公司集合、盈利链关系、Gate1–Gate4 结果、valuation_set、估值、左侧价值买点、左侧拐点买点和 Near-miss 都不跨轮持久化。

`research_state.json` 被禁止，不得创建、恢复或读取。跨轮基本面研究记忆只有 `data/research/industry_state.json`。
