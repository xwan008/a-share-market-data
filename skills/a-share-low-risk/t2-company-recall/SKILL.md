# 分层公司召回 Skill

## 目的
把“想起哪些股票”从模型自由回忆改成“公司全集先枚举 → 逐公司分类 → Registry持久化 → 硬审计”，同时把**产业链景气等级**与**公司是否值得继续验证**彻底拆开。

产业链状态只回答“行业证据有多强”，不能被当成断崖式公司删除器：
- `T2`：产业链证据最强，直接公司召回；
- `T1`：产业链已有实质改善但确认度不足，仅在存在显式 exposure rule 时进入**条件公司召回**；
- `unconfirmed`：不自动召回、不自动升级；若强公司盈利信号出现，只生成 `review_required`，反向要求重查产业链证据。

模型只判断已枚举公司是否有实质暴露，不负责凭记忆列公司名单，也不得因为某家公司盈利强就反向升级产业状态。

## 输入
- 已通过 Validator 的 `data/research/pipeline/industry_scan.json`
- `status=T2` 的全部细分链
- `status=T1` 且 `config/t2_exposure_rules.json` 已存在显式暴露规则的细分链
- `data/research/company_industry_index.json`：从全主板公司机械构建的申万行业归属索引
- `data/research/company_industry_registry.json`：历史已验证公司-产业链映射
- `config/t2_exposure_rules.json`
- 公开上市公司业务资料、行业资料、公司官网/年报/公告等独立来源

## 禁止
- 不读取周度盈利池。
- 不用估值、涨幅、技术、市值、龙头属性提前筛公司。
- 不允许从模型记忆直接列“代表公司”后宣称召回完成。
- company index / registry / 公司盈利都只能用于公司召回与验证，绝不能反向修改产业状态。
- 不允许把 `T1` 当作 `T2`；T1进入召回只代表“值得接受更严格的公司级验证”。
- `unconfirmed` 公司异常强只能触发产业链复核，不能自动进入共同池。

## 固定算法
### A. T2：直接召回
对每条T2细分链必须执行完整召回；缺少 exposure rule 属于硬错误。

### B. T1：条件召回
对当前T1细分链：
- 如果存在显式 exposure rule，执行与T2同等严格的机械公司枚举与逐公司暴露分类，并标记 `industry_status=T1`、`recall_mode=conditional_t1`；
- 如果暂时没有 exposure rule，不得静默消失，必须进入顶层 `t1_rule_coverage_gaps`；
- T1公司后续必须通过高于T2普通门槛的公司盈利确认，且每条T1链正式共同池最多1个代表，直到产业链独立升级为T2。

### C. unconfirmed：反向触发，不自动召回
`unconfirmed_reverse_trigger_rules` 只定义“哪些强公司信号值得重开产业链研究”。后续盈利扫描若触发规则，输出 `review_required`；产业链仍保持unconfirmed，必须重新检查价格/价差、库存、开工、订单、需求等领先变量后才能改变行业状态。

### D. 每条被召回链的机械公司分类
1. 先列出 `value_chain_links`，每个环节必须对应明确的直接盈利暴露。
2. **机械生成候选全集**：从 `company_industry_index.json` 取 `registry_broad_industry_id == 本链 broad_industry_id` 的全部主板公司；再并入规则中的 explicit exposed、已验证跨行业映射以及索引未知公司。不得由模型缩小候选全集。
3. **索引缺口兜底**：company index 的所有 `missing_codes` 与 `unmapped_codes` 对每条强制T2链都属于“归属未知、不能静默排除”的候选；条件T1也使用同一机械枚举原则。
4. **逐公司分类**：候选全集中的每一个股票代码必须在 `classifications` 中得到 `exposed / not_exposed / uncertain` 之一，不得静默跳过。
5. 每个 classification 至少记录 `status`、`reason`、`industry_status`、`recall_mode`；`exposed` 必须有证据并进入某个 value_chain_link。
6. **跨行业二次检索**：围绕“细分链名称 + 关键产品/工艺/客户场景”对全主板执行业务关键词/产业资料检索，记录 `cross_industry_search_queries` 与 `cross_industry_discoveries`。
7. 跨行业新发现经验证后写入 company registry；跨行业发现只能补公司，不能修改产业状态。
8. **Registry连续性**：已有 active 映射不得因为本次模型没想起来就消失；只有明确 `invalidation_reason` 才能标 inactive。
9. 对每个价值链环节输出 `registry_count`、`new_discovery_count`、`company_count`、`companies`、`coverage_gap`。
10. 候选全集未100%分类、存在uncertain、跨行业搜索未执行或存在未解释缺口时，本链 `recall_status=incomplete`。

## 输出
`data/research/pipeline/t2_company_recall.json`

保留历史文件名和 `t2_subchains` 字段以兼容下游，但 schema v3 后该数组表示“当前被允许进行公司召回的产业链”，其中可同时包含 T2 direct 与配置完备的 T1 conditional。

关键字段示例：
```json
{
  "schema_version": 3,
  "industry_scan_frozen_at": "ISO8601",
  "weekly_pool_read": false,
  "recall_policy": {
    "T2": "mandatory direct company recall",
    "T1": "conditional recall only with explicit exposure rule",
    "unconfirmed": "reverse-trigger review only"
  },
  "t1_rule_coverage_gaps": [["chemicals", "磷化工"]],
  "t2_subchains": [
    {
      "broad_industry_id": "chemicals",
      "subchain": "聚氨酯/MDI/TDI",
      "industry_status": "T1",
      "recall_mode": "conditional_t1",
      "candidate_universe_count": 123,
      "classifications": {
        "600309": {
          "status": "exposed",
          "reason": "对MDI/TDI/聚氨酯材料存在直接或实质业务暴露",
          "industry_status": "T1",
          "recall_mode": "conditional_t1",
          "evidence_sources": ["公司公开业务资料"]
        }
      },
      "recall_status": "complete"
    }
  ]
}
```

## 完成条件
- industry scan 的全部T2链必须一一出现，且缺少T2 exposure rule直接失败。
- 当前全部T1链必须满足审计闭合：**要么已条件召回，要么明确列入 `t1_rule_coverage_gaps`**；禁止静默消失。
- 被召回链的 `classifications` 必须与机械候选全集100%闭合，classification_counts必须可重算。
- 所有 `exposed` 公司必须进入对应 value_chain_link；所有 `uncertain` 必须显式记录。
- 跨行业二次搜索必须有查询记录；新发现必须被分类并进入相应价值链/Registry。
- `weekly_pool_read=false`。
- `T1`条件召回不得被描述为产业升级。
- `unconfirmed`反向触发不得直接把公司加入共同池。
