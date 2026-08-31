# A股低风险研究 V2 Skills

V2采用Prompt-first：Prompt做当期开放式公开研究，Skill保留长期纪律，代码维护机械数据。

核心链：`固定Coverage → 全市场景气发现 → 盈利链拆解 → 链内公司验证/比较 → 分类估值 → 价格结构 → Completion Gate → 当前机会`。

18:00从当前全市场重新开始，不存在周度机会池、候选池、T2池或跨期公司池。研究过程中的行业/盈利链/公司集合只属于本次执行，最终只写一个`research_state.json`。

Manifest `authoritative_data`是**仓库持久化机械数据白名单**，不是全部证据来源。18:00必须实时使用公开基本面证据：公司公告/财报、交易所、官方统计、行业协会/产业数据、订单/产销、产品价格/价差、库存/开工/利用率等。公开证据不另存成跨期研究缓存。

四个Skill：orchestrator负责研究顺序/Coverage/完成门；company-research负责公司盈利证据；valuation负责估值；price-structure负责时机。
