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
3. **索引缺口兜底**：company index 的所有 `missing_codes` 与 `unmapped_codes` 对每条T2链都属于“归属未知、不能静默排除”的候选，必须一起进入本链分类；这样即使行业索引本身不完整，也不会把潜在相关公司无声漏掉。
4. **逐公司分类**：候选全集中的每一个股票代码都必须在 `classifications` 中得到一种结果：`exposed / not_exposed / uncertain`。允许分批研究，但不得静默跳过任何代码。
5. 每个 classification 至少记录 `status` 与 `reason`；`exposed` 必须有原始公司证据并进入某个 value_chain_link；`uncertain` 必须说明缺失什么证据，并使该链 recall_status=incomplete；`not_exposed` 可用公司主营/行业资料给出简短排除理由。
6. **跨行业二次检索**：在机械候选全集之外，必须围绕“细分链名称 + 关键产品/工艺/客户场景”对全主板执行业务关键词/产业资料检索，用来发现申万一级行业不同但存在重要第二业务的公司。记录 `cross_industry_search_queries` 和 `cross_industry_discoveries`。这一步是搜索发现，不允许靠模型记忆补公司。
7. 跨行业新发现经验证后写入 company registry；以后即使模型注意力变化，active映射也不会消失。跨行业发现只能补公司，不能修改产业状态。
8. **Registry连续性**：已有 active 映射不得因为本次模型没想起来就消失；只有明确 `invalidation_reason`（业务退出/重组/退市/证据被推翻）才能标 inactive。
9. 对每个价值链环节输出：`registry_count`、`new_discovery_count`、`company_count`、`companies`、`coverage_gap`。
10. 若候选全集未100%分类、存在uncertain、跨行业搜索未执行、或存在未解释覆盖缺口，整条链 `recall_status=incomplete`，不得进入“全量召回完成”。

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
      "classifications": {
        "002475": {
          "status": "exposed",
          "reason": "高速铜连接业务可实质影响AI数据中心收入",
          "evidence_sources": ["公司半年报"]
        },
        "000001": {
          "status": "not_exposed",
          "reason": "主营与该细分链无实质业务暴露"
        }
      },
      "classification_counts": {
        "exposed": 5,
        "not_exposed": 118,
        "uncertain": 0
      },
      "cross_industry_search_queries": ["高速铜连接 A股 上市公司"],
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
- 每条T2链候选全集 = 对应 broad industry 全部索引公司 ∪ active registry映射 ∪ company index全部missing/unmapped代码。
- `classifications` 的代码集合必须与候选全集100%相等。
- classification_counts必须由 classifications 实际统计得到并闭合。
- 所有 `exposed` 公司都必须进入对应 value_chain_link；所有 `uncertain` 都使链 incomplete。
- 跨行业二次搜索必须有查询记录；新发现必须被分类并进入相应价值链/Registry。
- Registry已有active映射必须进入对应召回，除非有明确失效理由。
- `weekly_pool_read=false`。
- 任一未解释覆盖缺口使该链 incomplete。
