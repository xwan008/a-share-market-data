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
- 本地完整解析 `data/shards/*.json`，形成一级行业财务/核心盈利 breadth；
- 记录证据来源、参考日期、更新频率和 freshness；
- 生成 `data/research/industry_evidence.json`；
- 生成 `data/research/evidence_gate.json`；
- 发布与单一 commit SHA 绑定的 `a-share-production-bundle`。

### ChatGPT / Decision Layer
负责：
- 基于已准备证据判断 `improving / neutral / deteriorating / uncertain`；
- 解释领先变量如何传导到盈利；
- 对冲突证据做有限补查；
- 后续三级准入、公司 Gates、估值与榜单。

Evidence Layer 不得机械输出“行业景气结论”替代 Decision Layer。

## 2. 固定证据槽位
每个申万一级行业至少包含：
- `leading_anchor`：领先变量/第一锚；
- `earnings_confirmation`：最新盈利兑现；
- `negative_evidence`：反向证据或经过明确范围扫描后的反向 breadth。

每条证据必须带：
- `source`；
- `reference_date`；
- `frequency`；
- `freshness.status`。

不得用“今天没有新月度数据”把正常月频指标误判 stale。新鲜度必须按指标自身发布频率计算。

## 3. 全 shard 财务宽度层
Evidence Layer 每轮必须完整读取本地 `data/shards/*.json`，只使用 shard 自带 `industry_mapping_status / sw_level3_code` 向上归并申万一级行业，形成：
- mapped company count；
- financial usable count；
- 扣非利润/扣非 EPS 同比可用数量；
- core improving breadth；
- core deteriorating breadth；
- revenue improving breadth；
- headline profit deteriorating breadth（仅作一次性损益污染交叉提示）。

必须记录：
`shard_file_count / actual_shard_content_read_count / stock_records_read`。
Evidence Gate 必须要求 `actual_shard_content_read_count == shard_file_count`，否则连 shadow evidence shape 都不得视为有效。

该层回答“盈利是否已经兑现/是否存在广泛反向盈利证据”，**不能代替 leading_anchor**。因此即使某行业盈利 breadth 很强，没有订单、价格、库存、销量、利用率等第一锚时仍只能是 partial。

## 4. Shadow → Strict 迁移
当前 `config/industry_evidence_contract.json -> rollout_mode=shadow`：
- Evidence Gate 只输出覆盖诊断；
- 不阻断旧正式生产；
- `decision_layer_ready=false` 时 production bundle 仅用于诊断。

只有满足以下条件后才能切换 strict：
1. 31/31 一级行业全部 accounted；
2. 全 shard 财务 breadth 扫描完整；
3. 所有 required evidence slots 均有适配数据源；
4. freshness 规则经过至少数个交易日验证；
5. 证据源失败时能稳定标记 partial/missing，而不是生成伪证据；
6. `evidence_gate.strict_pass=true` 能稳定产生；
7. orchestrator 明确切换为 production bundle 消费模式。

## 5. 当前适配器
当前已迁移的结构化输入：
- 全行业：`data/shards/*.json` 提供财务/核心盈利 breadth 与反向 breadth；
- 有色金属：`health.commodity_anchors` 中 CU0/AU0/AL0/AO0 提供商品第一锚；
- 已有三级基线的行业：`industry_state.json` 提供额外的三级盈利状态交叉验证。

下一阶段只需集中补齐 `leading_anchor` adapter。制造/科技/消费/医药分别接订单、出货、价格、库存、利用率、资本开支、招投标、销量/需求等；资源品接商品价格、价差、库存与供需。

## 6. 禁止事项
- 禁止为了让 strict_pass 通过而把未检查的缺失证据写成 `checked_none`；
- 禁止把股价/K线强弱当作产业景气第一锚；
- 禁止使用上一轮榜单或公司名单作为行业召回边界；
- 禁止 Evidence Layer 直接生成最终股票候选；
- 禁止在 shadow 阶段提前移除现有正式研究硬门。
