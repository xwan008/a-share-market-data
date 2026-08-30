# 分层公司召回 Skill

## 目的
把“想起哪些股票”从模型自由回忆改成“公司全集先枚举 → 逐公司分类 → Registry持久化 → 硬审计”，同时把**产业链景气等级**与**公司是否值得继续验证**彻底拆开。

产业链状态只回答“行业证据有多强”，不能被当成断崖式公司删除器：
- `T2`：产业链证据最强，直接公司召回；
- `T1`：产业链已有实质改善但确认度不足，必须得到完整处理：要么建立显式 exposure rule 并进入**条件公司召回**，要么明确委托给更具体、仍处于T1/T2且已有完整规则的子链；
- `unconfirmed`：不自动召回、不自动升级；若强公司盈利信号出现，只生成 `review_required`，反向要求重查产业链证据。

模型只判断已枚举公司是否有实质暴露，不负责凭记忆列公司名单，也不得因为某家公司盈利强就反向升级产业状态。

## 输入
- 已通过 Validator 的 `data/research/pipeline/industry_scan.json`
- `status=T2` 的全部细分链
- `status=T1` 的全部细分链：必须在 `config/t2_exposure_rules.json` 中拥有直接规则或明确 delegation
- `data/research/company_industry_index.json`：从全主板公司机械构建的申万行业归属索引
- `data/research/company_industry_registry.json`：历史已验证公司-产业链映射，必须作为候选与暴露证据的一部分真正读取，不得只在文档中声明
- `config/t2_exposure_rules.json`
- 公开上市公司业务资料、行业资料、公司官网/年报/公告等独立来源

## 禁止
- 不读取周度盈利池。
- 不用估值、涨幅、技术、市值、龙头属性提前筛公司。
- 不允许从模型记忆直接列“代表公司”后宣称召回完成。
- company index / registry / 公司盈利都只能用于公司召回与验证，绝不能反向修改产业状态。
- 不允许把 `T1` 当作 `T2`；T1进入召回只代表“值得接受更严格的公司级验证”。
- `unconfirmed` 公司异常强只能触发产业链复核，不能自动进入共同池。
- 不允许为了清零T1覆盖缺口，把“化纤”“铜矿/冶炼”“电解铝/氧化铝”等父级聚合链粗暴重复召回；当父链内部盈利驱动已明确分化时，必须拆子链或使用显式 delegation。
- 不允许长期保留 `t1_rule_coverage_gaps`；当前T1存在任何未处理gap都属于硬失败。

## 固定算法
### A. T2：直接召回
对每条T2细分链必须执行完整召回；缺少 exposure rule 属于硬错误。

### B. T1：条件召回或子链委托
对每条当前T1细分链必须二选一：
1. **direct conditional recall**：存在显式 exposure rule，执行与T2同等严格的机械公司枚举与逐公司暴露分类，并标记 `industry_status=T1`、`recall_mode=conditional_t1`；公司后续必须通过高于T2普通门槛的盈利确认，每条T1链正式共同池最多1个代表，直到产业链独立升级为T2。
2. **delegated coverage**：父级T1本身是聚合链，且其内部不同环节盈利驱动明显分化；可明确委托给一个更具体、当前仍为T1/T2且已有完整公司暴露规则的子链。必须记录 `reason` 和 `residual_policy`，说明为何不重复召回以及父链剩余部分未来如何拆分验证。

`direct conditional recall ∪ delegated coverage` 必须与当前全部T1集合完全闭合，`t1_rule_coverage_gaps` 必须为空。

### C. unconfirmed：反向触发，不自动召回
`unconfirmed_reverse_trigger_rules` 定义“哪些已验证直接暴露公司的强盈利信号值得重开产业链研究”。反向触发必须扫描该链当前完整的已验证暴露全集，而不是手工指定一只触发股票。若盈利扫描触发规则，输出 `review_required`；产业链仍保持unconfirmed，必须重新检查价格/价差、库存、开工、订单、需求等领先变量后才能改变行业状态。

### D. 每条被召回链的机械公司分类
1. 先定义 `value_chain_link`，必须对应明确的直接盈利暴露。
2. **机械生成候选全集**：对应 broad industry 全部主板公司 ∪ company index 的 missing/unmapped ∪ exposure rule 的 explicit exposed ∪ company registry 中该链所有 active 映射。不得由模型缩小候选全集。
3. **Registry连续性**：active registry mapping 本身构成可验证暴露证据；已有映射不得因为本轮关键词未命中或模型没想起来而消失，只有明确 `invalidation_reason` 才能标 inactive。
4. **逐公司分类**：候选全集中的每一个股票代码必须得到 `exposed / not_exposed / uncertain` 之一，不得静默跳过。
5. 每个 classification 至少记录 `status`、`reason`、`industry_status`、`recall_mode`；`exposed` 必须有证据并进入 value_chain_link。
6. **跨行业二次检索**：围绕“细分链名称 + 关键产品/工艺/客户场景”对全主板执行业务关键词/产业资料检索，记录 `cross_industry_search_queries` 与 `cross_industry_discoveries`。
7. 跨行业新发现经验证后写入 company registry；跨行业发现只能补公司，不能修改产业状态。
8. 对每个价值链环节输出 `registry_count`、`new_discovery_count`、`company_count`、`companies`、`coverage_gap`。
9. 候选全集未100%分类、存在uncertain、跨行业搜索未执行或存在未解释缺口时，本链 `recall_status=incomplete`。

## 输出
`data/research/pipeline/t2_company_recall.json`

保留历史文件名和 `t2_subchains` 字段以兼容下游；schema v4 后该数组表示“当前实际执行公司召回的产业链”，同时包含 T2 direct 与 T1 conditional。父级T1委托另记在 `t1_delegated_coverage`。

关键字段：
```json
{
  "schema_version": 4,
  "industry_scan_frozen_at": "ISO8601",
  "weekly_pool_read": false,
  "recall_policy": {
    "T2": "mandatory direct company recall",
    "T1": "conditional recall or explicit delegation",
    "unconfirmed": "reverse-trigger review only"
  },
  "t1_rule_coverage_gaps": [],
  "t1_delegated_coverage": [
    {
      "broad_industry_id": "chemicals",
      "subchain": "化纤",
      "coverage_mode": "delegated_to_more_specific_chain",
      "delegate_broad_industry_id": "chemicals",
      "delegate_subchain": "氨纶",
      "reason": "父链品种盈利驱动分化",
      "residual_policy": "其余品种拆成独立直接盈利子链后再召回"
    }
  ],
  "t2_subchains": [
    {
      "broad_industry_id": "pharma",
      "subchain": "创新药",
      "industry_status": "T1",
      "recall_mode": "conditional_t1",
      "candidate_universe_count": 123,
      "classifications": {},
      "recall_status": "complete"
    }
  ]
}
```

## 完成条件
- industry scan 的全部T2链必须一一出现，且缺少T2 exposure rule直接失败。
- 当前全部T1链必须100%闭合：**直接条件召回或明确子链委托二选一**；`t1_rule_coverage_gaps` 必须为空。
- delegation目标必须是当前T1/T2、拥有有效exposure rule且实际被召回；委托链与直接召回链不得重复。
- 被召回链的 `classifications` 必须与机械候选全集100%闭合，classification_counts必须可重算。
- 所有 `exposed` 公司必须进入对应 value_chain_link；所有 `uncertain` 必须显式记录。
- Registry active映射必须进入候选全集并保持连续性。
- 跨行业二次搜索必须有查询记录；新发现必须被分类并进入相应价值链/Registry。
- `weekly_pool_read=false`。
- `T1`条件召回不得被描述为产业升级。
- `unconfirmed`反向触发不得直接把公司加入共同池。
