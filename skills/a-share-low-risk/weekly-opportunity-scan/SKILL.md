# 周度全市场盈利机会扫描 Skill

## 目的
把周度补漏池从“模型自由想起若干公司”改成“主板全集机械枚举 → 轻量宽召回 → 深度盈利验证 → 持久状态迁移”。本 Skill 只补公司，不参与或反向影响产业 T0/T1/T2。

## 前置条件
- `industry_scan` 与 `t2_company_recall` 已通过 Validator 并冻结。
- `weekly_pool_read_at >= t2_recall_frozen_at`。
- 输入主板全集来自 `data/research/company_industry_index.json` / 最新主板行情全集；不得由模型自行缩小。

## 固定算法
1. `UNIVERSE_ENUMERATION`：机械枚举全部主板股票代码，记录 `universe_count` 与代码集合摘要。
2. `LIGHT_RECALL`：对全集逐只给出 `pass / reject / uncertain` 轻量状态。允许使用最新财报/预告/快报、订单、产销、价格/成本、利用率、产品放量、客户扩产、库存、份额、一致盈利预期等；不得用股价、估值、技术、近期涨幅做召回过滤。
3. 轻量 `pass/uncertain` 才进入深验。深验固定回答：未来1–2季度核心驱动、传导链、支持/反向证据、一次性利润影响、失效条件。
4. 只有未来盈利方向为 `up` 或明确 `inflection_up` 且证据可验证者才进入/保留周度池。
5. 周期/资源公司必须识别直接商品/价差锚；仅“低PE+历史高增长”不得入池。
6. 与旧周度池做状态迁移：`新发现 / 继续保留 / 盈利强化 / 盈利转弱 / 移除`。旧 active 候选不得无原因消失，移除必须写 `removal_reason`。
7. 输出只记录公司级机会，不写或修改产业景气状态；即使某一行业集中出现候选，也只能记录为公司证据，留待下一次独立 `industry-scan` 验证。

## 输出
阶段审计写入 `data/research/pipeline/weekly_opportunity_scan.json`，持久池写入 `data/research/weekly_fundamental_opportunity_pool.json`。

阶段审计至少包含：
```json
{
  "schema_version": 1,
  "t2_recall_frozen_at": "ISO8601",
  "weekly_pool_read_at": "ISO8601",
  "universe_count": 3177,
  "screened_count": 3177,
  "screen_results": {
    "000001": {"status": "reject", "reason": "..."},
    "000338": {"status": "pass", "reason": "..."}
  },
  "deep_verified_codes": ["000338"],
  "pool_active_codes": ["000338"],
  "removed_codes": [],
  "industry_state_modified": false
}
```

## 完成条件
- `screened_count == universe_count`，且所有主板代码都有轻量状态；不能静默漏股。
- `industry_state_modified=false`。
- 深验通过的 active 公司均有未来1–2季度传导链与失效条件。
- 旧 active 公司只能显式迁移，不能因本次模型未想起而消失。
- 周度池读取时间晚于T2召回冻结时间。
- Validator FAIL 时不得把本周周度池标记为正式更新完成。
