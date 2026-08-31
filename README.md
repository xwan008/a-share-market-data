# A-share Market Data + Low-risk Research Bridge

This repository keeps the A-share low-risk workflow deliberately small and auditable.

## Active architecture

There are **three data workflows** plus one lightweight CI workflow:

1. **Update A-share market data** — weekdays at 16:10 and 16:30 Asia/Shanghai. It refreshes closed-session quotes, repairs qfq corporate-action drift, appends bounded history, rebuilds compact bridge data, and rebuilds the full-market mechanical price-structure input.
2. **Backfill A-share rolling history** — weekly Saturday 10:20 or manual only. It repairs bounded 180-session qfq history and longer-window summaries. It is deliberately not triggered by ordinary code/test pushes.
3. **Build SW taxonomy and company industry index** — weekly Sunday 09:20. It refreshes the fixed Shenwan 2021 31/134/346 Coverage taxonomy and the main-board stock → SW level1/2/3 mapping.
4. **CI** — tests code/config/Skill contract changes without writing market data.

## Low-risk research rule sources

Runtime rules are loaded in this order:

- `config/research_runtime_policy.json`
- `config/research_pipeline_manifest.json`
- the four `skills/a-share-low-risk/*/SKILL.md` files named by the Manifest

The Manifest is intentionally small: it owns machine contracts, authoritative paths, fixed Coverage counts, stage order and output contracts. Detailed research methodology lives in the Skills. Research prompts execute the current rules and should not maintain a second long-lived copy.

## Authoritative research data

The low-risk research task may read only current Manifest `authoritative_data` paths:

- `config/industry_scan_universe.json` — fixed SW2021 Coverage nodes (31/134/346), not an answer pool
- `data/research/company_industry_index.json` — main-board company → SW level1/2/3 mapping
- `data/research/v2/full_market_price_structure.json` — mechanical timing input
- `data/latest.json` — latest reliable closed-session market snapshot
- `data/history_shards/*.json` — bounded history
- `data/research/v2/research_state.json` — current research state, when a valid full run exists

Legacy pipeline outputs, industry buckets, persistent T2 registries and weekly opportunity pools are intentionally absent from main. Git history remains the audit trail.

## Research state compatibility

`research_state.manifest_schema` must equal the current Manifest `schema_version`. A mismatch is stale and cannot be used as the current baseline. If no valid state exists, the 18:00 full run rebuilds from current authoritative inputs; the 06:00 run must not substitute an old Git-history result.

## Market-history invariant

Only completed daily sessions are persisted. Full OHLCV history is bounded to 180 sessions per stock; compact longer-window summaries may be rebuilt during the weekly refresh. Price structure answers **when**, while valuation answers **what it is worth**.
