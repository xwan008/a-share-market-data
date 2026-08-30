# 未来盈利验证 Skill

## 目的
对已召回公司逐只验证未来1–2季度盈利方向，并在公司级盈利验证后进行细分产业链代表性压缩。历史财报只验证，不作为唯一准入理由；产业链状态只决定证据门槛，不等于整条链所有公司自动进入正式候选。

核心原则：
- `T2 direct`：产业链证据强，使用标准公司级盈利确认门槛；
- `T1 conditional`：产业链确认度较低，只有公司自身盈利传导明显更强时才可进入代表竞争，且每条T1链最多1个正式代表；
- `unconfirmed reverse-trigger`：公司异常强只触发产业链复核，不自动升级行业、不自动进入共同池。

## 输入
- 分层公司召回池 `data/research/pipeline/t2_company_recall.json`
- 产业冻结结果
- 产业主流程冻结后才可读取的周度盈利补漏池
- 全市场轻量盈利扫描结果（仅用于已配置unconfirmed反向触发审计）
- `config/t2_representative_policy.json`
- `config/t2_exposure_rules.json`

## 每家公司固定验证
必须形成：
1. `earnings_model_type`：commodity_spread / order_volume / commercialization / utilization_mix / other
2. `forward_driver`：未来1–2季度最重要领先变量
3. `transmission_chain`：领先变量 → 收入/价格/毛利率 → 利润
4. `evidence_for` / `evidence_against`
5. `direction`：up / flat / down / uncertain
6. `confidence`：high / medium / low
7. `invalidation_condition`

机器共同池必须至少保留 `gate_mode`、`recall_tags`、`t2_tags`、`conditional_t1_tags`、当前盈利指标、gate_status、reason、forward_bridge 与 invalidation_condition，保证每一次准入或拒绝可追溯。

## 三路径准入
### A. T2 direct：标准公司级盈利门槛
T2说明产业链本身已经有较强证据，但公司仍不能自动通过。当前唯一机器规则在 `config/t2_representative_policy.json`：
- 净利润必须为正；
- 排除ST；
- YoY路径：净利润同比 ≥15% 且收入同比 ≥5%；或
- QoQ路径：最新季度净利润环比 ≥20% 且收入同比 ≥0%。

通过后才能进入T2代表性压缩。

### B. T1 conditional：更严格公司确认
T1不是弱化版T2，也不是自动通过。公司只有在自身盈利证据显著更强时才能继续：
- 净利润必须为正；
- 排除ST；
- YoY路径：净利润同比 ≥25% 且收入同比 ≥8%；或
- QoQ路径：最新季度净利润环比 ≥35% 且收入同比 ≥3%。

即使通过，仍只代表“公司证据足够强，可以作为T1条件候选”，**不代表产业链已升级为T2**。

每条T1细分链正式共同池最多1个代表。若未来产业链通过独立行业证据升级为T2，才切换到T2代表上限规则。

### C. unconfirmed reverse-trigger：只重开产业研究
对 `config/t2_exposure_rules.json` 的 `unconfirmed_reverse_trigger_rules`：
- 若全市场轻量扫描已经给出强盈利 `pass`；或
- 净利润为正、非ST，最新季度净利润环比 ≥50% 且收入同比 ≥0%；
则标记该产业链 `review_required`。

`review_required` 只意味着必须重新检查产品价格/价差、库存、开工、订单、需求、成本等产业领先变量。它不能：
- 自动把unconfirmed改成T1/T2；
- 自动把触发公司加入共同池；
- 绕过公司暴露验证、行业冻结与后续代表性规则。

## 代表性压缩
### T2细分链
对通过公司级门槛并带T2标签的公司：
- 通过数 ≤4：最多1家；
- 5–12家：最多2家；
- >12家：最多3家；
- 具体数量以 `config/t2_representative_policy.json` 为唯一机器规则。

### T1细分链
无论通过公司级门槛的公司有多少，正式共同池最多1家，直到产业链独立升级T2。

代表性排序以“绝对盈利规模 + 当前盈利兑现”为主：利润规模抑制低基数百分比暴增误选，利润/收入同比与环比确认景气是否真正传导到公司。禁止使用估值、近期涨幅、技术结构或R:R，以保持左/右侧及估值阶段独立。

周度全市场深验属于更强的公司级证据，在同一已召回链内部享有优先级，但仍受到对应链代表上限约束。只有没有当前召回标签、由周度全市场独立发现的公司，才作为独立候选保留。

多标签公司必须接受全局约束。一家公司被选中后，不得导致其任一所属链超过代表上限；处理顺序优先T2 direct，再处理T1 conditional，避免T1通过跨标签挤掉T2正式代表。

未被选中的同行不删除研究记录，标记 `deferred_by_subchain_diversification`，继续保留在宽召回/盈利验证审计中，但不得进入 `common_pool_codes`。

## 淘汰/延期只允许基于
- 未来盈利链明显失效；
- 基本面质量明显不足；
- 一次性利润主导；
- T1公司未达到更严格公司确认门槛；
- 同一直接盈利驱动高度重复且代表性更差；
- 细分链正式候选名额已被更强代表公司占用。

禁止用估值、近期涨幅、技术形态、R:R提前淘汰。

## 输出审计
共同池至少输出：
- `t2_representative_selection`
- `conditional_t1_representative_selection`
- `unconfirmed_reverse_trigger_audit`
- `unconfirmed_review_required_tags`
- `future_earnings_gate`
- `common_pool_codes`

每只进入共同资格池的公司必须能回答：“未来1–2季度利润为什么继续改善/为什么会出现拐点？”回答不了则不得伪装成正式盈利向上。

这样同时保证：
1. T2宽召回不漏直接暴露公司；
2. T1优秀公司不会因产业确认度差一级而在公司验证前被整链删除；
3. unconfirmed强公司能反向暴露行业研究缺口，但不能倒逼行业结论；
4. 正式共同池仍然保持低风险、可审计和代表性约束。
