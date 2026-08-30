# 公司盈利研究 Skill

## 目的
从正在改善的盈利驱动链与全市场盈利异常中召回直接受益公司，并验证未来1–2季度盈利是否真实、可持续。**召回宁宽，正式淘汰必须发生在公司级证据之后。**

## 三个召回来源
`COMPANY_RECALL = driver_exposure ∪ earnings_anomaly ∪ weekly_full_market_recall`

1. `driver_exposure`：公司对active盈利驱动有直接、实质业务暴露。
2. `earnings_anomaly`：全市场财报/预告/快报出现收入、利润、毛利、现金流或订单异常改善；仅用于补漏召回。
3. `weekly_full_market_recall`：现有周度宽召回数据资产，仅作为补漏来源。

## 机械召回不是盈利验证
归母净利润同比/环比只回答“是否值得进一步看”，不能证明盈利质量。估值队列形成后，必须自动补充财报级证据，优先读取东方财富主要财务指标，失败可回退新浪财务指标。

机器证据至少包括：
- 扣非净利润、扣非EPS；
- 扣非净利润同比/环比（可用时）；
- 每股经营现金流、经营现金流/收入或经营现金流/净利润；
- 一次性收益占归母利润比例；
- TTM扣非EPS。

### TTM扣非EPS
统一使用：
`TTM扣非EPS = 2025全年扣非EPS + 2026H1扣非EPS - 2025H1扣非EPS`

禁止用“2026H1扣非EPS × 2”简单年化制造伪精度。

## Production盈利证据硬门槛
正式盈利证据至少满足：
- `research_status = pass`；
- Forward Bridge成立；
- 扣非净利润与扣非EPS为正；
- 一次性因素占归母利润原则上不超过35%；
- 现金流质量通过：每股经营现金流/经营现金流占收入至少一项非负，或经营现金流/净利润达到约30%以上；
- 非风险警示证券。

任一项缺失都进入明确blocker，不允许被综合评分修复。若扣非亏损或一次性因素占比超过50%，原`pass`应降为`quality_review_required`。

## 公司级固定研究
每家公司必须回答：
- `why_now`；
- `driver_links`及暴露纯度；
- 收入、归母、扣非变化；
- `margin_quality`；
- `cashflow_quality`；
- `one_off_risk`；
- `forward_bridge`；
- `evidence_for / evidence_against`；
- `invalidation_condition`；
- `earnings_direction`与`earnings_confidence`。

## 代表性压缩
估值前每条Driver原则上保留3–5家，优先考虑直接暴露、扣非兑现、行业地位、Bridge持续性和现金流质量。禁止在此阶段使用估值、股价涨幅、技术结构淘汰公司。

## 反向发现
强公司盈利异常无法映射现有driver时输出`driver_review_required`，不得静默删除。

## 输出
`data/research/v2/company_research.json`

每只公司必须能解释：`从哪里召回 → 对什么驱动有暴露 → 扣非/主营为什么改善 → 现金流是否支持 → 未来1–2季度为什么继续 → 什么会推翻`。
