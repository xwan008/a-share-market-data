# T2公司召回 Skill

## 目的
把“想起哪些股票”从模型自由回忆改成“持久化Registry优先 + 逐产业环节补充发现 + 硬审计”的召回流程。

## 输入
- 已通过 Validator 的 `data/research/pipeline/industry_scan.json`
- 仅其中 `status=T2` 的细分链
- `data/research/company_industry_registry.json`：历史已验证公司-产业链映射
- 公开上市公司业务资料、行业分类、公司官网/年报/公告等独立来源

## 禁止
- 不读取周度盈利池。
- 不用估值、涨幅、技术、市值、龙头属性提前筛公司。
- 不允许只列“代表公司”后宣称全量召回。
- company registry 只能用于公司召回，绝不能反向升级产业状态。

## 固定算法
对每条T2细分链：
1. 先列出 `value_chain_links`，每个环节必须对应明确的直接盈利暴露。
2. **Registry优先召回**：先从 `company_industry_registry.json` 读取所有仍有效的对应映射；已有映射不得因为本次模型没想起来就消失。
3. **增量发现**：每个环节再独立检索沪深主板实质业务暴露公司，至少用两类独立公开来源核对覆盖；发现Registry未记录的公司时加入本次召回。
4. **持久化回写**：新验证映射写回 company registry；旧映射只有出现明确 `invalidation_reason`（业务退出/重组/退市/证据被推翻）才能移除或标记inactive。
5. 每家公司记录：
   - code/name
   - broad_industry_id/subchain/value_chain_link
   - exposure_summary
   - exposure_materiality = high/medium/uncertain
   - status = active/inactive
   - first_verified_at/last_verified_at
   - evidence_sources（至少1条公司原始资料；覆盖核对总体至少2类独立来源）
   - invalidation_reason（inactive时必填）
6. 对每个价值链环节必须给出：`registry_count`、`new_discovery_count`、`company_count`、`companies`、`coverage_gap`。
7. 若某环节数据不足，不得静默跳过，写 `coverage_gap` 并将整条链 `recall_status=incomplete`。

## 输出
`data/research/pipeline/t2_company_recall.json`
```json
{
  "schema_version": 1,
  "industry_scan_frozen_at": "ISO8601",
  "weekly_pool_read": false,
  "t2_recall_frozen_at": "ISO8601",
  "t2_subchains": [
    {
      "broad_industry_id": "electronics",
      "subchain": "高速连接器/铜互连",
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
- 每条T2链至少1个价值链环节；每个环节有公司列表或明确无符合主板公司/数据不足说明。
- `weekly_pool_read=false`。
- Registry已有active映射若未出现在本次对应T2召回中且没有明确失效理由，Validator应判失败。
- 任何未解释环节缺口使该链 incomplete。
