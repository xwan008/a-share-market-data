# 产业景气扫描 Skill

## 目的
把“想起哪些行业”从模型职责中移除。扫描对象必须来自 `config/industry_scan_universe.json`，模型只负责逐项判断。

## 输入
- `config/industry_scan_universe.json`
- 当前公开产业数据、商品/价差、订单/出货/库存/利用率/审批/终端销售等证据
- 上一期 `industry_scan.json`（若存在，仅用于状态迁移）

## 禁止输入
本阶段禁止读取 `weekly_fundamental_opportunity_pool.json` 及其中任何公司、行业、盈利逻辑。

## 执行算法
对 Registry 中每一个 `broad_industry`：
1. 逐一枚举其 `minimum_subchains`，不得筛热门后再研究。
2. 对每条细分链独立建立：
   - `direct_profit_driver`
   - `leading_variables`
   - `evidence_for`
   - `evidence_against`
   - `future_1_2q_transmission`
   - `status` = T0/T1/T2/unconfirmed/not_applicable
   - `stage` = early/mid/late/null
   - `invalidation_condition`
3. minimum_subchains 是下限。发现独立盈利驱动的新细分链时加入 `dynamic_subchains`，但不得替换/跳过已有 minimum_subchains。
4. 大行业不能直接成为T2判断单位。
5. 公司财报只能作为“盈利传导证据”，不能作为扫描入口。

## T0/T1/T2
- T0：至少1个领先变量方向改善，盈利传导可解释但证据薄。
- T1：≥2条独立证据，或“领先变量持续改善 + 1条盈利传导证据”。
- T2：领先变量继续有效，且盈利传导已落到利润/价差/订单/产销/毛利/现金流等结果，无重大反向证据。

## 输出
写入 `data/research/pipeline/industry_scan.json`：
```json
{
  "schema_version": 1,
  "scan_as_of": "YYYY-MM-DD",
  "weekly_pool_read": false,
  "industry_frozen_at": "ISO8601",
  "broad_industries": [
    {
      "id": "nonferrous",
      "name": "有色金属",
      "subchains": [
        {
          "name": "电解铝/氧化铝",
          "registry_source": "minimum",
          "status": "T1",
          "stage": null,
          "direct_profit_driver": "铝价-氧化铝-电力成本价差",
          "leading_variables": [],
          "evidence_for": [],
          "evidence_against": [],
          "future_1_2q_transmission": "...",
          "invalidation_condition": "..."
        }
      ],
      "coverage_gap": []
    }
  ]
}
```

## 完成条件
只有 Validator 证明：
- Registry 所有 broad_industry 均存在；
- 每个 minimum_subchain 均有唯一明确状态；
- `weekly_pool_read=false`；
- 无静默缺口；
才能标记产业扫描 PASS。
