# T2公司召回 Skill

## 目的
把“想起哪些股票”从模型自由回忆改成“公司全集先枚举 → 逐公司分类 → Registry持久化 → 硬审计”。模型只判断已枚举公司是否有实质暴露，不负责凭记忆列公司名单。

## 输入
- 已通过 Validator 的 `data/research/pipeline/industry_scan.json`
- 仅其中 `status=T2` 的细分链
- `data/research/company_industry_index.json`：从全主板公司机械构建的申万行业归属索引
- `data/research/company_industry_registry.json`：历史已验证公司-产业链映射
- 公开上市公司业务资料、行业资料、公司官网/年报/公告等独立来源

## 禁止
- 不读取周度盈利池。
- 不用估值、涨幅、技术、市值、龙头属性提前筛公司。
- 不允许从模型记忆直接列“代表公司”后宣称召回完成。
- company index / registry 只能用于公司召回，绝不能反向升级产业状态。

## 固定算法
对每条T2细分链：
1. 先列出 `value_chain_links`，每个环节必须对应明确的直接盈利暴露。
2. **机械生成候选全集**：从 `company_industry_index.json` 取 `registry_broad_industry_id == 本T2链 broad_industry_id` 的全部主板公司；再并入 `company_industry_registry.json` 中该细分链所有 active 映射。不得由模型缩小这个候选全集。
3. **逐公司分类**：候选全集中的每一个股票代码都必须得到一种结果：`exposed / not_exposed / uncertain`。允许分批研究，但不得静默跳过任何代码。
4. 判断 `exposed` 时至少记录：所属价值链环节、业务暴露摘要、是否足以实质影响未来1–2季度利润、原始公司证据。对 secondary business / 多业务公司，只要该业务可能实质影响利润就保留。
5. **跨行业补充发现**：公开资料若发现申万一级行业不同但确有该细分链实质暴露的公司，加入 `cross_industry_discoveries`；验证后写入 company registry。跨行业发现只能补公司，不能修改产业状态。
6. **Registry连续性**：已有 active 映射不得因为本次模型没想起来就消失；只有明确 `invalidation_reason`（业务退出/重组/退市/证据被推翻）才能标 inactive。
7. 对每个价值链环节输出：`registry_count`、`new_discovery_count`、`company_count`、`companies`、`coverage_gap`。
8. 若 company industry index 对该 broad industry 存在未解释缺口，或候选全集未全部分类，整条链 `recall_status=incomplete`，不得进入“全量召回完成”。

## 输出
`data/research/pipeline/t2_company_recall.json`
```json
{
  "schema_version": 1,
  "industry_scan_frozen_at": "ISO8601",
  "company_index_generated_at": "ISO8601",
  "weekly_pool_read": false,
  "t2_recall_frozen_at": "ISO8601",
  "t2_subchains": [
    {
      "broad_industry_id": "electronics",
      "subchain": "高速连接器/铜互连",
      "candidate_universe_count": 123,
      "evaluated_codes": ["000000"],
      "classification_counts": {
        "exposed": 5,
        "not_exposed": 116,
        "uncertain": 2
      },
      "cross_industry_discoveries": [],
      "value_chain_links": [
        {
          "name": "高速铜连接组件",
          "registry_count": 1,
          "new_discovery_count": 0,
          "company_count": 1,
          "companies": [
            {
              "code": "002475",
              "name": "立讯精密",
              "exposure_summary": "...",
              "exposure_materiality": "high",
              "evidence_sources": ["..."]
            }
          ],
          "coverage_gap": []
        }
      ],
      "recall_status": "complete",
      "coverage_gap": []
    }
  ]
}
```

## 完成条件
- industry scan 的所有T2链必须一一出现。
- 每条T2链的候选全集由 company industry index 机械生成，`evaluated_codes` 必须覆盖100%。
- classification_counts 总数必须等于 candidate_universe_count。
- 所有 `exposed` 公司都必须进入对应 value_chain_link。
- Registry已有active映射必须进入对应召回，除非有明确失效理由。
- `weekly_pool_read=false`。
- 任一未解释覆盖缺口使该链 incomplete。
