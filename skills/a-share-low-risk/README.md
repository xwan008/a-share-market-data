# A股低风险研究 Skills

这是正式生产研究链，不使用 shadow，也不通过递增数字 schema 管理研究规则。

唯一主链：

`Data Gate → 每次全市场/全行业召回 → taxonomy映射 → 三级行业盈利状态 → 公司全集扫描 → Gate1→Gate4 → 完整估值 → reasonable_buy_range + low_risk_buy_range → 独立价格结构 → 左侧价值买点榜 → 左侧拐点买点榜 → Near-miss → Completion Gate → 正式发布`

## 状态边界
跨期只允许保留一类基本面研究状态：
- `data/research/industry_state.json`：紧凑的三级行业盈利基线，是唯一跨期基本面记忆。

机械价格结构独立保存为 `data/research/full_market_price_structure.json`，它属于市场机械数据，不属于上一轮研究结果。

**不持久化上一轮正式榜单。** 公司、盈利链关系、估值、合理买入区、低风险买入区、两类买点、Near-miss 和最终榜单均只存在于本轮执行上下文；下一轮必须重新生成。

禁止周度机会池、候选池、T2池、独立公司池、估值缓存和 `research_state.json`。

## 发现与刷新不是一回事
景气发现每次运行都从全市场/完整申万一级行业重新召回，不能被上一期方向限制。

周度/日度差异只作用于三级行业深度盈利研究：周度重验当前发现方向下的相关三级行业基线；日度只对有新增或变化证据的三级节点做深度刷新。

## 公司准入
允许进入公司层的三级状态：
- `trend=improving`；
- `trend=stable AND breadth=divergent`。

后者只扩大研究资格，不降低公司、估值或买点门槛。

## 四个价格概念必须分开
- `reasonable_price_range`：合理价值区，大致回答“值多少钱”；
- `reasonable_buy_range`：正常合理买入区，回答“什么价格已经值得左侧参与”；
- `safe_price_ceiling`：在 `base_fair_value` 上应用一次MOS后的高安全边际价格上限；
- `low_risk_buy_range`：更严格的低风险/高安全边际窄执行区。

正常估值路径固定为：

`reasonable_buy_range.lower = reasonable_price_range.lower`

`reasonable_buy_range.upper = base_fair_value`

`safe_price_ceiling = base_fair_value × (1 - MOS)`

`low_risk_buy_range = [safe_price_ceiling × 0.95, safe_price_ceiling]`

`reasonable_buy_range` 不使用MOS；5%只是 `low_risk_buy_range` 的窄执行带宽，不是第二次MOS。旧 `safe_price_range` 字段继续废弃，其历史窄带语义迁移到 `low_risk_buy_range`，不得再迁移到 `reasonable_buy_range`。

## 当前价格位置
必须同时描述两层位置：
- `valuation_position = above_reasonable_buy_range / inside_reasonable_buy_range / below_reasonable_buy_range`；
- `low_risk_position = above_low_risk_buy_range / inside_low_risk_buy_range / below_low_risk_buy_range`。

价格低于 `reasonable_buy_range.lower` 时先做 `discount_sanity_check`，不能因为“更便宜”机械淘汰；复核仍有效且没有跌破 `low_risk_buy_range.lower` 时，可标记 `deeper_discount`，仍保留左侧价值资格。只有低于 `low_risk_buy_range.lower` 才进入 `deep_discount_review`，完成复核和重新估值前不入正式价值榜或Near-miss。

## 两个正式榜单
### 左侧价值买点榜
`left_value_buyable_now = current_price <= reasonable_buy_range.upper AND valuation_review_valid AND NOT deep_discount_review`

正常进入 `reasonable_buy_range` 即具有左侧价值资格；更深折价只要复核通过也不能被机械排除。进入 `low_risk_buy_range` 时增加 `low_risk=true` / 高安全边际标签，而不是把低风险窄带当作唯一买点门槛。

技术结构尚未确认不能把已经成立的价值资格淘汰，只需要明确结构风险。

### 左侧拐点买点榜
`left_value_buyable_now AND left_turn_confirmed`

拐点榜是左侧价值榜的子集，只收“已经具备价值资格 + 开始出现止跌/转折确认”的公司。

因此本系统不使用“价值 × 右侧结构交集 = 唯一买点”的旧逻辑，也不发布单一 `buyable_now` 榜。

## Near-miss
Near-miss只收 `current_price > reasonable_buy_range.upper` 的非review公司，距离必须以 `reasonable_buy_range.upper` 为锚。禁止用 `low_risk_buy_range.upper` 或 `safe_price_ceiling` 做Near-miss排序。

## 证据
Manifest `authoritative_data` 是仓库机械数据白名单，不是全部证据来源。正式研究必须使用当前公开基本面证据：公司公告/财报、交易所、官方统计、行业协会/产业数据、订单/产销、产品价格/价差、库存/开工/利用率等。

## 四个 Skill
- `orchestrator`：总流程、Data Gate、行业/公司Gate、Completion Gate、双榜发布；
- `company-research`：盈利链公司全集召回、轻筛、横向比较、去重；
- `valuation`：核心盈利、三级同行相对估值、合理价值区、合理买入区与低风险买入区；
- `price-structure`：独立技术结构与左侧拐点确认。

规则契约由 `config/research_runtime_policy.json` 与 `config/research_pipeline_manifest.json` 共同定义；修改规则时应同步更新相关Skill与契约测试，而不是增加 schema 序号。若旧契约仍保留“reasonable_buy_range=低风险5%窄带”的历史定义，以新版 `valuation/SKILL.md` 与 `orchestrator/SKILL.md` 的双买入区语义为准，并应在后续契约迁移时删除该旧定义。
