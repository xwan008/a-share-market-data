# 价格结构 Skill

## 目的
只回答现在是否适合参与。价格结构不能回答公司值多少钱，也不能反向修改合理价格或安全价格。

## 全市场独立扫描
对全部具备新鲜历史数据的主板股票做机械结构扫描；扫描不依赖本期基本面研究是否已研究到某家公司；风险警示证券可扫描但不能因此获得低风险资格；历史价格只用于结构和位置判断。

## 状态
`base_not_started`、`transition`、`breakout`、`pullback`、`trend_continuation`、`overheated`、`damaged`。用于描述，不扩张成复杂交易状态机。

## 必查信息
最近高低点/关键突破位、HH/HL或LH/LL、成交量、收盘位置、相对市场/行业强度、中短期均线/关键成本区、加速或乖离。机械阈值必须可校准。

## 与价值组合
价值合理+未启动→观察；价值合理+健康突破/回踩→可重点研究分批参与；价格显著高于合理区→不追；便宜但结构破坏→左侧观察；价值不成立→再强结构也不是低风险基本面买点。

## 进入机会综合的最低输出
`structure_type`、`key_level`、`relative_strength`、`volume_confirmation`、`chase_risk`、`timing_action`、`structure_invalidation`。

## 持久化
全市场机械结构写`full_market_price_structure.json`；本次研究公司的结构判断只写本次`research_state.json`，不形成独立公司集合或跨期缓存。
