# A股低风险研究编排 Skill

## 目标
把低风险榜从“一个长提示词自由展开”改为有固定输入、阶段产物和硬验收的研究流水线。模型只判断由 Registry/公司全集机械枚举出的对象，不负责凭注意力想起行业、产业链或公司。

## 唯一编排入口
先读取 `config/research_pipeline_manifest.json`。Manifest列出的 Registry、Skill、Validator 和阶段顺序是权威流程；不得根据聊天上下文临时改写召回范围。

## 固定输入
- `config/industry_scan_universe.json`：产业最小覆盖全集。
- `data/research/company_industry_index.json`：全主板公司机械行业索引；缺失/未映射代码不能静默排除。
- `data/research/company_industry_registry.json`：已验证的公司-细分链持久映射。
- `data/health.json`、`data/backfill_status.json`：行情/历史数据健康。
- `data/research/weekly_fundamental_opportunity_pool.json`：仅在产业主流程和T2召回冻结后读取。
- 各阶段 Skill：`industry-scan`、`t2-company-recall`、`earnings-validation`、`cycle-valuation`、`technical-structure`。

## 固定阶段
0. `COMPANY_INDEX_HEALTH`
   - 读取公司行业索引并校验完整性。
   - 索引缺失/未映射的主板代码不直接淘汰；在每条T2链公司分类时作为“归属未知候选”强制评估。
1. `INDUSTRY_SCAN`
   - 禁止读取周度盈利池。
   - 读取产业覆盖全集，对每个大行业和每条 minimum_subchain 产生明确状态。
   - 输出 `data/research/pipeline/industry_scan.json`。
   - Validator失败则停止正式主流程。
2. `T2_RECALL`
   - 只读取已验证 industry scan 中的T2细分链。
   - 候选公司由 company index + active company registry + index未知代码机械生成，不允许模型缩小全集。
   - 每个代码必须分类为 exposed/not_exposed/uncertain；还必须执行跨行业第二业务搜索发现。
   - 输出 `data/research/pipeline/t2_company_recall.json`。
   - Validator失败则停止。
3. `WEEKLY_MERGE`
   - 只有产业扫描和T2召回 PASS 后才读取周度池。
   - 记录 `weekly_pool_read_at`，必须晚于 `industry_frozen_at` 和 `t2_recall_frozen_at`。
4. `EARNINGS_VALIDATION`
   - 对合并后的每只公司逐只验证未来1–2季度盈利链。
   - 禁止估值/技术条件提前淘汰。
5. `LEFT_VALUE`
   - 非周期公司：前瞻E → 合理估值 → 价值锚。
   - 周期公司：调用 cycle-valuation Skill，商品/价差情景先于盈利中枢。
6. `RIGHT_STRUCTURE`
   - 使用覆盖最近完整交易日的数据。
   - 结构 → 多周期压力 → 第一压力 → 空间 → R:R。
7. `INTERSECTION_AND_FINAL`
   - 左右榜冻结后才取交集和Top3。

## 信息隔离
- `INDUSTRY_SCAN` 与 `T2_RECALL` 完成并冻结前不得读取周度池内容。
- 周度池只能补公司，不能新增/升级产业状态。
- company index/registry同样只能用于公司召回，不能影响产业T0/T1/T2。
- provenance若显示周度池提前读取，整次运行 INVALID。

## 失败原则
- 产业Registry覆盖不完整：停止，不允许宣称全行业扫描完成。
- T2候选公司全集未100%分类：该T2链召回 incomplete。
- 任一 uncertain 公司、未执行跨行业二次搜索、active Registry映射丢失：对应T2链 incomplete。
- 某只股票历史K线缺失：只隔离该股票右侧，不拖垮其他完整候选。
- 无合格Top3允许空榜。

## 最终产物必须可追溯
任何公司都必须能回答：
`它为什么在机械候选全集中/从哪条周度补漏进入 → 为什么判定有/无该产业暴露 → 为什么未来盈利成立 → 左侧E和估值怎么得到 → 右侧第一压力来自哪个周期 → 最终在哪一步保留/淘汰`。
