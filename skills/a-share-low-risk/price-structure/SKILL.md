# 价格结构 Skill

## 目的
只回答“现在是否适合参与、若参与从什么价格区间进入、哪里失效”。价格结构不能回答公司值多少钱，也不能反向修改合理价格或安全价格。

## 全市场独立扫描
对全部具备新鲜历史数据的主板股票做机械结构扫描；扫描不依赖本期基本面是否研究该公司。历史价格只用于结构、关键位和入场时机判断。

## 状态
`base_not_started`、`transition`、`breakout`、`pullback`、`trend_continuation`、`overheated`、`damaged`。

## 必查信息
最近高低点/关键突破位、HH/HL或LH/LL、成交量、收盘位置、相对市场/行业强度、中短期均线/关键成本区、加速或乖离。

## 结构入场区间
对进入本期估值集合的公司必须额外输出：
- `structure_type`；
- `structure_entry_range`：仅由支撑、突破确认位、回踩承接区、量价和乖离推导的技术入场区间，可为空；
- `structure_invalidation`：结构失效价/条件；
- `key_level`；
- `relative_strength`；
- `volume_confirmation`；
- `chase_risk`；
- `timing_action`。

`structure_entry_range`不能参考合理价或安全价来人为调整；它必须独立产生，然后由Buy Point Contract与安全价格区求交集。

## 时机规则
- `pullback / breakout / trend_continuation`在量价、关键位和追高风险满足时可成为timing eligible；
- `damaged / overheated`不能成为当前低风险买点；
- `base_not_started / transition`默认观察，除非后续确认转入有效结构；
- 结构有效但价值不成立，仍不能进入低风险买点。

## 与价值组合
价格结构只提供WHEN和结构失效条件。最终`buy_price_range = safe_price_range ∩ structure_entry_range`。若无交集，当前不是买点；不得扩大技术区间或价值区间来制造交集。

## 持久化
全市场机械结构写`full_market_price_structure.json`；本次研究公司的结构判断写本次`research_state.json`，不形成独立公司集合或跨期缓存。
