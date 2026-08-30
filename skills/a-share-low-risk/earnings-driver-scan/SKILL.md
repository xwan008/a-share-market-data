# 盈利驱动扫描 Skill

## 目的
识别当前正在改善、可能在未来1–2季度继续传导到上市公司利润的“细分盈利驱动链”。研究单位不是宽泛行业，也不是T1/T2等级，而是可以解释到收入、价格、成本、毛利或销量的具体驱动。

## 核心原则
- 大行业只用于导航，不用于准入。
- 同一大行业下可以同时存在强、弱、改善、恶化的不同细分链。
- `confidence`只表达证据强弱，不参与估值折价。
- 公司财报可以作为盈利传导证据，也可以反向暴露遗漏的驱动链，但不能靠单个公司自动证明整条产业链景气。

## 输入
- `config/industry_scan_universe.json`：仅作为覆盖提示，不再强制输出T0/T1/T2。
- 商品/产品价格与价差、订单、出货、库存、开工率、产能利用率、终端需求、审批/招标、产销数据。
- 公司财报/预告/快报中的主营盈利变化。
- 上一期V2 driver scan用于状态迁移。

## 每条驱动链必须回答
1. `driver_name`：例如制冷剂配额与价差、MDI/TDI价差、AI服务器出货、高端PCB升级、重卡更新、创新药商业化。
2. `profit_mechanism`：驱动变量如何影响收入/销量/成本/毛利率/净利润。
3. `leading_variables`：未来1–2季度最重要的3–5个领先变量。
4. `direction`：improving / stable / deteriorating / uncertain。
5. `confidence`：high / medium / low，仅作证据标签。
6. `evidence_for` / `evidence_against`。
7. `future_1_2q_transmission`。
8. `invalidation_condition`。
9. `company_exposure_hints`：只记录已验证的直接业务暴露线索，不在本阶段做正式公司筛选。

## 动态发现
除了已有覆盖提示，还必须允许新增动态驱动链。若全市场盈利异常集中出现在某一业务环节，应创建 `review_required_driver` 并研究其产品价格/订单/需求/成本证据，而不是因为Registry没有该名字就忽略。

## 禁止
- 不输出T1/T2作为主流程控制字段。
- 不因为大行业整体一般，就压掉细分链机会。
- 不因为大行业整体强，就把所有子行业都判成机会。
- 不用股价、估值、技术形态决定盈利驱动是否成立。

## 输出
V2 shadow期写入：`data/research/v2/earnings_driver_scan.json`。

完成条件：每一条active driver都能用一句完整因果链解释“什么变量变好 → 哪个盈利科目受益 → 为什么未来1–2季度可能继续”。
