# 公司盈利研究 Skill

## 目的
从“正在改善的盈利驱动链”与全市场盈利异常中召回直接受益公司，并验证公司自身未来1–2季度盈利是否真实、可持续。召回宁可稍宽，淘汰必须发生在公司级证据之后。

## 三个召回来源
`COMPANY_RECALL = driver_exposure ∪ earnings_anomaly ∪ weekly_full_market_recall`

1. `driver_exposure`：公司对active盈利驱动有直接、实质业务暴露。
2. `earnings_anomaly`：全市场财报/预告/快报出现主营收入、扣非利润、毛利率、现金流或订单的异常改善；用于发现遗漏驱动。
3. `weekly_full_market_recall`：保留现有周度全市场宽召回数据资产，作为补漏来源，不再单独构成业务Skill。

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

## 通过原则
正式研究候选必须至少满足：
- 主营或扣非盈利有改善证据，而非仅归母利润表观增长；
- 未来1–2季度存在可验证Bridge；
- 一次性收益没有掩盖主营恶化；
- 数据不足时显式 `insufficient_evidence`，不得猜。

不设置T1/T2不同门槛。驱动链证据强弱只进入`earnings_confidence`，不作为断崖式准入等级。

## 代表性压缩
估值前只做轻压缩，每条盈利驱动链原则上保留3–5家研究候选。

排序优先：
1. 直接业务暴露纯度；
2. 主营/扣非盈利兑现质量；
3. 行业地位与规模；
4. 未来Bridge持续性；
5. 现金流与财务质量。

禁止在此阶段使用估值、股价涨幅、技术结构、R:R淘汰公司。估值后再决定每条链最终展示1–2家，避免“最便宜的第二代表”在估值前被删掉。

## 反向发现
如果强公司盈利异常无法映射到现有driver，输出 `driver_review_required`，要求回到`earnings-driver-scan`研究新的产品/订单/成本驱动；不得把公司静默删除。

## 输出
V2 shadow期写入：`data/research/v2/company_research.json`。

每只公司必须能回答：`从哪里被召回 → 对什么盈利驱动有暴露 → 盈利为什么改善 → 未来1–2季度为什么可能继续 → 什么会推翻`。
