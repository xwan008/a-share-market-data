# A股低风险研究编排 Skill

## 目标
把低风险榜从“一个长提示词自由展开”改为有固定输入、阶段产物和硬验收的研究流水线。模型只判断已枚举对象，不负责凭注意力想起行业或跳过阶段。

## 固定输入
- `config/industry_scan_universe.json`：产业最小覆盖全集。
- `data/health.json`、`data/backfill_status.json`：行情/历史数据健康。
- `data/research/weekly_fundamental_opportunity_pool.json`：仅在产业主流程冻结后读取。
- 各阶段 Skill：`industry-scan`、`t2-company-recall`、`earnings-validation`、`cycle-valuation`、`technical-structure`。

## 固定阶段
1. `INDUSTRY_SCAN`
   - 禁止读取周度盈利池。
   - 读取产业覆盖全集，对每个大行业和每条 minimum_subchain 产生明确状态。
   - 输出 `data/research/pipeline/industry_scan.json`。
   - 执行 `python scripts/validate_research_pipeline.py industry-scan ...`；失败则停止。
2. `T2_RECALL`
   - 只读取已验证的 `industry_scan.json` 中 T2 细分链。
   - 逐链先枚举价值链环节，再召回主板公司。
   - 输出 `data/research/pipeline/t2_company_recall.json`。
   - Validator失败则停止。
3. `WEEKLY_MERGE`
   - 只有前两阶段 PASS 后才读取周度池。
   - 记录 `weekly_pool_read_at`，必须晚于 `industry_frozen_at` 和 `t2_recall_frozen_at`。
4. `EARNINGS_VALIDATION`
   - 对合并后的每只公司逐只验证未来1–2季度盈利链。
   - 输出共同资格池；禁止估值/技术条件提前淘汰。
5. `LEFT_VALUE`
   - 非周期公司：前瞻E → 合理估值 → 价值锚。
   - 周期公司：必须调用 cycle-valuation Skill，商品/价差情景先于盈利中枢。
6. `RIGHT_STRUCTURE`
   - 必须使用覆盖最近完整交易日的历史数据。
   - 结构 → 多周期压力 → 第一压力 → 空间 → R:R。
7. `INTERSECTION_AND_FINAL`
   - 左右榜冻结后才取交集和Top3。

## 信息隔离
- 在 `INDUSTRY_SCAN` 与 `T2_RECALL` 完成并冻结前，不得读取周度池内容。
- 周度池只能补公司，不能新增/升级产业状态。
- 若 provenance 显示周度池读取时间早于产业冻结，整次运行 INVALID。

## 失败原则
- 覆盖不完整：停止，不允许宣称“全行业扫描完成”。
- T2价值链环节未闭合：该T2链不得进入正式召回完成状态。
- 某只股票历史K线缺失：只隔离该股票右侧，不拖垮其他完整候选。
- 无合格Top3允许空榜。

## 最终产物必须可追溯
任何公司都必须能回答：
`它从哪条细分链/周度池被召回 → 为什么未来盈利成立 → 左侧E和估值怎么得到 → 右侧第一压力来自哪个周期 → 最终在哪一步保留/淘汰`。
