# 公司盈利研究 Skill

## 目的
从正在改善的盈利驱动链与全市场盈利异常中召回直接受益公司，并验证未来1–2季度盈利是否真实、可持续。**召回宁宽，正式淘汰必须发生在公司级证据之后。**

## 三个召回来源
`COMPANY_RECALL = driver_exposure ∪ earnings_anomaly ∪ weekly_full_market_recall`

1. `driver_exposure`：公司对active盈利驱动有直接、实质业务暴露。
2. `earnings_anomaly`：全市场财报/预告/快报出现收入、利润、毛利、现金流或订单异常改善；仅用于补漏召回。
3. `weekly_full_market_recall`：现有周度宽召回数据资产，仅作为补漏来源。

## 机械召回不是盈利验证
机械层的归母净利润同比/环比只能回答“值得不值得进一步看”，不能证明盈利质量。若机械数据源不提供扣非净利润，必须显式标记 `recurring_profit_unverified`，不得把归母高增替代为扣非改善。

机械层允许附带以下复核信号，但这些信号原则上不直接删除普通公司：
- 经营现金流/每股经营现金流为负；
- 利润增速远高于收入，需排查低基数、投资收益、处置收益、补贴等；
- 当前仍亏损但出现环比改善；
- 毛利率/ROE等盈利质量指标异常。

风险警示证券仍可被全市场扫描用于覆盖与诊断，但**不得进入“低风险”主榜或Top机会**，这是Universe风险资格，不是个股黑名单。

## 公司级固定研究
每家公司必须回答：
- `why_now`：为什么本期值得研究；
- `driver_links`：对应哪些盈利驱动链，各自暴露纯度；
- `revenue_yoy / recurring_profit_yoy / qoq_profit`；
- `margin_quality`：毛利/净利率是否改善；
- `cashflow_quality`：经营现金流是否支持；
- `one_off_risk`：投资收益、处置收益、补贴等是否主导；
- `forward_bridge`：未来1–2季度具体传导链；
- `evidence_for / evidence_against`；
- `invalidation_condition`；
- `earnings_direction`：up / inflection_up / flat / down / uncertain；
- `earnings_confidence`：high / medium / low。

## 正式研究通过原则
至少满足：
- 主营或扣非盈利有改善证据，而非仅归母表观增长；
- 未来1–2季度存在可验证Bridge；
- 一次性收益没有掩盖主营恶化；
- 现金流与盈利差异得到解释；
- 数据不足时显式 `insufficient_evidence`，不得猜。

不设置T1/T2不同门槛。驱动证据强弱只进入`earnings_confidence`，不作为断崖式准入等级，也不得进入估值折价。

## 代表性压缩
估值前每条盈利驱动原则上保留3–5家，排序优先：
1. 直接业务暴露纯度；
2. 主营/扣非盈利兑现质量；
3. 行业地位与规模；
4. 未来Bridge持续性；
5. 现金流与财务质量。

禁止在此阶段使用估值、股价涨幅、技术结构、R:R淘汰公司。估值完成后再决定每条链最终展示1–2家。

## 反向发现
强公司盈利异常无法映射到现有driver时输出 `driver_review_required`，回到盈利驱动扫描研究产品/订单/成本原因，不得静默删除。

## 输出
V2 shadow期：`data/research/v2/company_research.json`。

每只公司必须能解释：`从哪里召回 → 对什么驱动有暴露 → 主营/扣非为什么改善 → 未来1–2季度为什么继续 → 什么会推翻`。
