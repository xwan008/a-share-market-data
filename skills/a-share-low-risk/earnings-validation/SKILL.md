# 未来盈利验证 Skill

## 目的
对已召回公司逐只验证未来1–2季度盈利方向。历史财报只验证，不作为唯一准入理由。

## 输入
- T2公司召回池
- 产业冻结结果
- 产业主流程冻结后才可读取的周度盈利补漏池

## 固定判断
每家公司必须形成：
1. `earnings_model_type`：commodity_spread / order_volume / commercialization / utilization_mix / other
2. `forward_driver`：未来1–2季度最重要的领先变量
3. `transmission_chain`：领先变量 → 收入/价格/毛利率 → 利润
4. `evidence_for` / `evidence_against`
5. `direction`：up / flat / down / uncertain
6. `confidence`：high / medium / low
7. `invalidation_condition`

## 淘汰只允许基于
- 未来盈利链明显失效；
- 基本面质量明显不足；
- 一次性利润主导；
- 同一直接盈利驱动高度重复且代表性明显更差。

禁止用估值、近期涨幅、技术形态、R:R提前淘汰。

## 输出要求
每只进入共同资格池的公司必须能用一句话回答：
“未来1–2季度利润为什么继续改善/为什么会出现拐点？”
回答不了则 direction=uncertain，不得伪装成正式盈利向上。
