# A股低风险研究 Skills

这套目录把原来的长 Prompt 拆成可版本化的研究能力。

## 核心原则
- **Registry决定必须研究什么**：`config/industry_scan_universe.json` 防止行业/产业链因注意力漂移被漏掉。
- **Skill决定怎么研究**：不同阶段有独立输入、输出和禁止事项。
- **持久化Registry记住公司映射**：`data/research/company_industry_registry.json` 防止已验证公司因为下一次模型没想起来而消失。
- **Validator决定能不能继续**：`scripts/validate_research_pipeline.py` 对覆盖与阶段顺序做硬验收，失败应停止后续正式榜单。
- **LLM只做判断，不负责凭记忆枚举全集**。

## Skills
1. `orchestrator`：阶段编排与信息隔离。
2. `industry-scan`：逐Registry细分链判断T0/T1/T2。
3. `t2-company-recall`：Registry优先、逐价值链环节召回公司并持久化。
4. `earnings-validation`：未来1–2季度盈利验证。
5. `cycle-valuation`：商品/价差 → 盈利 → 估值。
6. `technical-structure`：最新完整K线 → 多周期第一压力 → R:R。

## Validator
示例：

```bash
python scripts/validate_research_pipeline.py industry-scan data/research/pipeline/industry_scan.json
python scripts/validate_research_pipeline.py t2-recall data/research/pipeline/t2_company_recall.json --industry-scan data/research/pipeline/industry_scan.json
python scripts/validate_research_pipeline.py stage-order data/research/pipeline/run_state.json
```

Validator返回非零退出码时，不应继续正式核心榜/Top3。
