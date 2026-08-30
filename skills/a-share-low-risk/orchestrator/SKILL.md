# A股低风险研究编排 Skill

## 目标
把低风险榜从“一个长提示词自由展开”改为有固定输入、阶段产物和硬验收的研究流水线。模型只判断由 Registry/公司全集机械枚举出的对象，不负责凭注意力想起行业、产业链或公司；最终选择也不得绕过上游产物自行拍板。

## 唯一编排入口
先读取 `config/research_pipeline_manifest.json`。Manifest列出的 Registry、Skill、Validator 和阶段顺序是权威流程；不得根据聊天上下文临时改写召回范围、估值方法或最终选择标准。

## 固定输入
- `config/industry_scan_universe.json`：产业最小覆盖全集。
- `data/research/company_industry_index.json`：全主板公司机械行业索引；缺失/未映射代码不能静默排除。
- `data/research/company_industry_registry.json`：已验证公司-细分链持久映射。
- `data/health.json`、`data/backfill_status.json`：行情/历史数据健康。
- `data/research/weekly_fundamental_opportunity_pool.json`：只有主产业流程冻结后才能读取/更新。
- 各阶段 Skill：`industry-scan`、`t2-company-recall`、`weekly-opportunity-scan`、`earnings-validation`、`fundamental-valuation`、`cycle-valuation`、`technical-structure`、`final-selection`。

## 固定阶段
0. `COMPANY_INDEX_HEALTH`
   - 读取公司行业索引并校验完整性。
   - 索引缺失/未映射主板代码不直接淘汰；在每条T2链分类时作为未知候选强制评估。
1. `INDUSTRY_SCAN`
   - 严禁读取周度盈利池。
   - Registry机械枚举全部大行业和 minimum_subchain；逐项输出T0/T1/T2/unconfirmed/not_applicable。
   - 输出 `industry_scan.json`，Validator FAIL 则停止正式主流程。
2. `T2_RECALL`
   - 仅对已验证T2链执行。
   - company index + active registry + index未知代码机械生成候选全集；逐公司 exposed/not_exposed/uncertain，并执行跨行业第二业务检索。
   - 输出 `t2_company_recall.json`；候选未100%分类或覆盖不闭合则停止。
3. `WEEKLY_OPPORTUNITY_SCAN`
   - 只有前两阶段 PASS 后才允许读取旧周度池。
   - 周五18:00：从主板全集机械枚举，做轻量宽召回，再对 pass/uncertain 深验未来1–2季度盈利，状态迁移后更新周度池。
   - 非周五18:00：只读取最近已验证周度池，不重建。
   - 周度池只补公司，永不修改产业状态。
4. `STAGE_ORDER`
   - 记录并验证 industry freeze、T2 recall freeze、weekly read 的时间顺序；提前读取周度池使本次运行 INVALID。
5. `EARNINGS_VALIDATION`
   - 合并 T2召回池 ∪ 周度池并数量闭合后，对每家公司逐只验证未来1–2季度盈利链。
   - 禁止用估值/股价/技术条件提前淘汰。
6. `LEFT_VALUE`
   - 非周期公司调用 `fundamental-valuation`：前瞻盈利 → 合理估值 → 价值锚 → 当前价格位置。
   - 周期/资源公司调用 `cycle-valuation`：商品/价差 → 供需情景 → 公司盈利 → 估值 → 价值锚。
   - 两类输出都必须可追溯；估值不可得就显式 unavailable，不能猜。
7. `RIGHT_STRUCTURE`
   - 使用覆盖最近完整交易日的数据。
   - 结构 → 多周期压力地图 → 第一有效压力 → 上行空间 → 失效点 → R:R。
   - 单股数据缺失只隔离该股。
8. `FINAL_SELECTION`
   - 调用 `final-selection`。
   - 初始交集严格等于 LEFT_SET ∩ RIGHT_SET。
   - 终审只能从交集中做 core/watch/reject，不能把交集外股票补进核心榜。
   - Top3只来自core，第一目标原则上>=15%、R:R>=2；允许少于3只或空榜。
   - 上游 Validator FAIL 时不得生成正式core/Top3。

## 信息隔离
- `INDUSTRY_SCAN` 与 `T2_RECALL` 冻结前不得读取周度池。
- 周度池只能补公司，不能新增/升级产业状态。
- company index/registry只能用于公司召回，不能影响产业T0/T1/T2。
- 左侧与右侧必须基于同一共同资格池独立计算，不能互相提前过滤。
- FINAL_SELECTION只选择，不修复上游计算；发现问题必须 `return_to_stage`。

## 失败原则
- Registry产业覆盖不完整：停止，不允许宣称全行业扫描完成。
- T2候选全集未100%分类：对应链 incomplete。
- 周度主板全集未完成轻量筛选：周度池更新无效，继续使用最近有效版本并报告失败。
- 非周期正式价值锚缺少前瞻盈利/合理估值桥：valuation unavailable。
- 周期价值锚未完成商品锚链：valuation unavailable。
- 单股K线不完整：只隔离该股右侧。
- Final Validator不通过：不发布正式core/Top3。
- 无合格Top3允许空榜。

## 最终产物必须可追溯
任何公司都必须能回答：
`它为什么进入机械候选全集/从哪条周度补漏进入 → 为什么判定有/无产业暴露 → 为什么未来盈利成立 → 走哪一种估值Skill、E和估值怎么得到 → 右侧第一压力来自哪个周期 → 是否进入严格交集 → 终审在哪一步保留/淘汰`。
