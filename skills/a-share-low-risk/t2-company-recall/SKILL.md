# T2公司召回 Skill

## 目的
把“想起哪些股票”从模型自由回忆改成逐产业环节、可审计的召回流程。

## 输入
- 已通过 Validator 的 `data/research/pipeline/industry_scan.json`
- 仅其中 `status=T2` 的细分链
- 公开上市公司业务资料、行业分类、公司官网/年报/公告等独立来源

## 禁止
- 不读取周度盈利池。
- 不用估值、涨幅、技术、市值、龙头属性提前筛公司。
- 不允许只列“代表公司”后宣称全量召回。

## 固定算法
对每条T2细分链：
1. 先列出 `value_chain_links`，每个环节必须对应明确的直接盈利暴露。
2. 每个环节独立召回沪深主板实质业务暴露公司。
3. 每家公司记录：
   - code/name
   - value_chain_link
   - exposure_summary
   - exposure_materiality = high/medium/uncertain
   - evidence_sources（至少1条公司原始资料；覆盖核对总体至少2类独立来源）
4. 对每个价值链环节必须给出：`company_count`、`companies`、`coverage_gap`。
5. 若某环节数据不足，不得静默跳过，写 `coverage_gap` 并将整条链 `recall_status=incomplete`。

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
- 任何未解释环节缺口使该链 incomplete。
