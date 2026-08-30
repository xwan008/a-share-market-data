# 最终交集/终审/Top3 Skill

## 目的
把“最终拍板”从自由裁量改成可审计选择器。终审只选择已经通过上游计算的候选，不允许修补、覆盖或重算错误的价值锚与压力位。

## 输入
- 已冻结左侧价值结果。
- 已冻结右侧结构结果。
- 未来1–2季度盈利验证结果。
- 数据健康与各阶段 Validator 状态。

## 固定算法
1. `LEFT_SET`：仅保留左侧 `valuation_status=valid` 且满足既定安全边际/合理买入条件的公司。
2. `RIGHT_SET`：仅保留右侧 `data_status=verified`、结构有效且第一有效压力空间>=10%、R:R>=1.5 的公司。
3. `INITIAL_INTERSECTION = LEFT_SET ∩ RIGHT_SET`。不得从交集外“补一只看起来不错的”。
4. 对交集逐只终审：
   - future earnings 仍为 up/inflection_up 且未触发 invalidation；
   - 催化/预期尚未明显完全交易；
   - 第一有效压力、失效点与R:R输入完整；
   - 左侧价值锚来源完整；
   - 无重大数据缺口或上游 Validator FAIL。
5. 终审结果：`core / watch / reject`，每只必须给出明确原因。
6. Top3只能从 `core` 中按低风险质量排序；不得因数量不足放宽硬条件。
7. Top3原则：第一目标空间>=15%、R:R>=2；不满足则不能进入Top3。允许Top3少于3只或为空。
8. 若终审发现上游计算链缺字段/明显不一致，标记 `return_to_stage`（left/right/earnings），不得在终审现场自行纠正。

## 输出
`data/research/pipeline/final_selection.json`
至少包含：
- `left_set_codes`
- `right_set_codes`
- `initial_intersection_codes`
- `reviews`：每只的 core/watch/reject、理由、return_to_stage
- `core_codes`
- `top3_codes`
- `empty_reason`（若为空）
- `upstream_validator_status`
- `final_frozen_at`

## 完成条件
- `initial_intersection_codes` 必须严格等于 left/right 集合交集。
- `core_codes` 必须是交集子集。
- `top3_codes` 必须是 core 子集，数量<=3。
- 所有Top3满足第一目标空间>=15%与R:R>=2。
- 任一上游硬 Validator FAIL 时不得生成正式 core/Top3。
- 终审只选择，不修正上游基础计算。
