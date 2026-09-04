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
2. 在正式读取 shard 前先锁定当前生产仓库最新 `main` 的 commit SHA，记为 `repo_commit_sha`。本轮所有规则文件、运行时快照和 shard 正文必须能追溯到该 SHA；不得在同一轮中混用不同 commit 的 shard 数据。
3. 再枚举 `data/shards/` 下的全部 `*.json` 文件，记录 `shard_file_count`。
4. 对枚举出的每一个 shard，必须继续读取该文件**正文内容**；目录列表/contents API 返回的 name、path、sha、size 等元数据只用于枚举，不能代替正文扫描。
5. 若执行环境支持本地仓库或工作区，优先在 `repo_commit_sha` 对应的本地副本中直接遍历 `data/shards/*.json`；若使用 GitHub 连接器，则先枚举文件，再按 `path` 使用文件读取接口逐个读取正文。两种方式在 Completion Gate 语义上等价。
6. 若任一 shard 因响应大小限制、单行 JSON 截断、连接器输出预算、分页或其他传输限制而无法确认完整正文，**不得直接判定** `shard_scan_incomplete`。此时必须启动“锁定 SHA 的本地回退”：
   - 优先将 `repo_commit_sha` 对应的完整仓库归档/工作区副本物化到当前本地运行环境；
   - 若普通仓库 archive 通道在当前执行环境不可用，则查找 GitHub Actions 在同一 `repo_commit_sha` 上发布的 `a-share-runtime-snapshot` artifact，下载并解压到本地；
   - artifact 内的 `runtime_snapshot_manifest.json.commit_sha` 必须严格等于 `repo_commit_sha`，否则不得使用；
   - 本地回退成功后，直接逐文件 `json.loads` / 等价完整解析 `data/shards/*.json`，而不是继续依赖被截断的连接器文本输出。
7. 本地回退时必须记录 `scan_source`：普通本地仓库/归档记为 `local_commit_archive`，GitHub Actions runtime snapshot 记为 `github_actions_runtime_snapshot`；同时记录 `repo_commit_sha`、`shard_file_count`、`actual_shard_content_read_count`、`company_universe_count`。
8. 对每条股票记录直接使用 shard 自带的 `industry_mapping_status / sw_level3_code / sw_level3_name` 判断行业终态：
   - 映射缺失 → `industry_unmapped`
   - 已映射但不在 admitted Level-3 集合 → `industry_not_eligible`
   - 已映射且命中 admitted Level-3 集合 → `mapped+eligible`，进入 Gate1
9. `data/research/company_industry_index.json`、历史正式结果、旧候选、旧 Near-miss、搜索结果或聚合摘要均不得代替本步骤构造公司全集。
10. **禁止错误阻断**：仅因为目录 API 不能一次性返回全部 shard 正文、返回被分页/截断、只显示元数据，或单个 shard 的连接器文本输出被截断，不得判定 `shard_scan_incomplete`。只有在实际尝试逐文件读取后仍存在无法确认完整正文的 shard，且“锁定 SHA 的本地回退”（普通本地副本/归档 + 同 SHA runtime snapshot artifact）也均无法完成扫描时，才可认为 shard 内容扫描不完整。
11. Completion Gate 前必须核对：`repo_commit_sha`、`scan_source`、枚举文件数、实际成功完整读取文件数、处理股票记录数；`actual_shard_content_read_count` 必须等于 `shard_file_count`。

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

## 5. Gate3｜同类公司固定顺序逐级择优
Gate3 只做一件事：在 Gate2 已通过的公司中，找出真正同类的公司，并用固定、不可漂移的顺序选出当前最优代表。Gate3 禁止自由权重、综合打分或五维并行权衡。

### 5.1 可比组
先判断是否真正同类：
- 按主营业务和核心盈利驱动分组；
- 不以申万三级名称机械代替真实可比关系；
- 盈利来源、产业链位置或商业模式明显不同的公司，不得强行放在同一组比较；
- 只使用本轮 shard 已有结构化字段完成 Gate3，原则上不做公开资料深挖。

### 5.2 固定决胜顺序
同组公司必须严格按以下顺序逐级比较：

`核心盈利实力 → ROE → 经营现金流 → 估值`

不得改变顺序，不得自行调整权重，不得把后级指标与前级指标混合打分。

1. **核心盈利实力**：优先比较扣非归母净利润或等价核心利润的**绝对规模**；Gate2 已经负责确认其方向为改善，因此 Gate3 不得把“同比增速最高”直接等同于“核心盈利实力最强”。在核心盈利绝对规模与持续改善上已经能清晰分出优劣时，直接确定优先级，不再让后面的 ROE、现金流或估值反向推翻该结论。
2. **ROE**：只有当核心盈利实力接近、无法清晰区分时，才比较 ROE；ROE 明显更优者优先。若已能分出优劣，停止继续综合权衡。
3. **经营现金流**：只有当核心盈利实力与 ROE 仍接近时，才比较经营现金流兑现；优先选择利润能够更好转化为经营现金流、现金流质量更稳健的公司。
4. **估值**：只有前三层仍无法清晰区分时，才比较当前估值吸引力；优先参考 TTM PE / 动态 PE，必要时用 PB 与 ROE 做交叉检查。估值是最后决胜项，不得因为估值更便宜推翻前面已经明确更强的核心盈利实力。

固定原则：**前一级已经清晰分出优劣，就停止；只有前一级接近或无法可靠区分，才进入下一级。**

### 5.3 禁止事项
- 禁止使用 `earnings_realization / profitability_quality / valuation_attractiveness / business_purity / independent_advantage` 五维自由加权或综合打分；
- 禁止因为某家公司扣非利润增速最高就自动胜出；
- 禁止因为某家公司 PE 最低就越级胜出；
- 禁止为了保留更多优秀公司而人为拆细可比组；
- `business_purity`、成本、资源、产能、技术、产品、客户、渠道、结构性成长等信息可以用于判断“是否真正同类”或在 Gate4 深研中验证，但不再作为 Gate3 可自由加权的并列评分项。

### 5.4 强周期/资源公司边界
强周期/资源类公司在 Gate3 仍使用同一固定顺序：

`核心盈利实力 → ROE → 经营现金流 → 估值`

成本曲线/AISC、储量品位、未来 1–3 年产量、项目投产进度、商品价格敏感度、伴生品和周期下行风险等深层信息统一留到 Gate4，不得为了这些信息延长 Gate3。

### 5.5 Gate3终态
原则上每个真正同类的可比组只保留 1 家进入后续研究：
- `pass:best_in_group`
- `exclude:inferior_to_group_winner:<reason>`
- `research_uncertain:<reason>`

`research_uncertain` 仅用于关键结构化字段缺失、异常或口径冲突导致固定顺序无法可靠执行的极少数情况；“两家公司很接近”本身不是 research_uncertain 理由，必须继续进入下一层决胜。

所有 Gate3 排除必须指出公司是在固定顺序的哪一级落后，例如：`inferior_core_earnings_strength / inferior_roe / inferior_cash_conversion / inferior_valuation`。公司本身优秀不等于必须保留。

## 6. Gate4 / valuation_set
Gate3 通过公司进入公司级重点确认与后续完整估值。

- 按股票代码去重进入 `valuation_set`；
- 保留全部 `source_chain_ids`；
- 同一股票只执行一次完整估值、一次价格结构判断和一次买点评估；
- 所有进入 `valuation_set` 的公司必须逐只完整估值，不得因数量多而跳过。

## 7. 守恒诊断
每轮必须机械回答：
- `repo_commit_sha`；
- `scan_source`；
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
