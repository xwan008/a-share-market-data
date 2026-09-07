# 行业证据生产线 Skill

## 目标
把正式榜单中的“临场开放式行业搜索”前移为可重复、可审计的 Evidence Layer：

`市场数据完成 → 行业证据采集/结构化 → Evidence Gate → production bundle → ChatGPT Decision Layer`

本阶段为 **shadow rollout**。在 Evidence Gate 达到 strict_pass 之前，不得删除现有正式行业研究主线，也不得让影子证据包冒充已经完成的正式研究。

## 1. 职责边界

### GitHub Actions / Evidence Layer
负责：
- 固定申万2021一级行业全集；
- 为每个一级行业准备固定证据槽位；
- 记录证据来源、参考日期、更新频率和 freshness；
- 生成 `data/research/industry_evidence.json`；
- 生成 `data/research/evidence_gate.json`；
- 发布与单一 commit SHA 绑定的 `a-share-production-bundle`。

### ChatGPT / Decision Layer
负责：
- 基于已准备证据判断 `improving / neutral / deteriorating / uncertain`；
- 解释盈利传导机制；
- 对冲突证据做有限补查；
- 后续三级准入、公司 Gates、估值与榜单。

Evidence Layer 不得机械输出“行业景气结论”替代 Decision Layer。

## 2. 固定证据槽位
每个申万一级行业至少包含：
- `leading_anchor`：领先变量/第一锚；
- `earnings_confirmation`：最新盈利兑现；
- `negative_evidence`：反向证据或明确的已检查无重大反证记录。

每条证据必须带：
- `source`；
- `reference_date`；
- `frequency`；
- `freshness.status`。

不得用“今天没有新月度数据”把正常月频指标误判 stale。新鲜度必须按指标自身发布频率计算。

## 3. Shadow → Strict 迁移
当前 `config/industry_evidence_contract.json -> rollout_mode=shadow`：
- Evidence Gate 只输出覆盖诊断；
- 不阻断旧正式生产；
- `decision_layer_ready=false` 时 production bundle 仅用于诊断。

只有满足以下条件后才能切换 strict：
1. 31/31 一级行业全部 accounted；
2. 所有 required evidence slots 均有适配数据源；
3. freshness 规则经过至少数个交易日验证；
4. 证据源失败时能稳定标记 partial/missing，而不是生成伪证据；
5. `evidence_gate.strict_pass=true` 能稳定产生；
6. orchestrator 明确切换为 production bundle 消费模式。

## 4. 当前第一阶段适配器
第一阶段只迁移已经结构化、可靠的数据源：
- 有色金属：`health.commodity_anchors` 中 CU0/AU0/AL0/AO0；
- 所有可映射行业：`industry_state.json` 提供季度/半年度盈利兑现和三级 breadth 证据。

这并不意味着其他行业已经完成机器化。缺少订单、出货、库存、开工率、招投标、需求等第一锚时必须标记 partial/missing，并由后续 adapter 逐行业补齐。

## 5. 禁止事项
- 禁止为了让 strict_pass 通过而把缺失证据写成 `checked_none`；
- 禁止把股价/K线强弱当作产业景气第一锚；
- 禁止使用上一轮榜单或公司名单作为行业召回边界；
- 禁止 Evidence Layer 直接生成最终股票候选；
- 禁止在 shadow 阶段提前移除现有正式研究硬门。
