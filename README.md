# A-share Market Data + Low-risk Research Bridge

This repository contains the production A-share market-data layer and the single active low-risk research contract.

## Production baseline

- `main` is the only production development line.
- The low-risk runtime is fail-closed and reads only the repository inputs declared by `config/research_pipeline_manifest.json`, plus current public research evidence required by the Skills.
- Git history and archived branches are audit/recovery material only and are never runtime research inputs.

## Active workflows

1. **Update A-share market data** — weekdays after the A-share close; refreshes quotes, fundamentals, rolling history, bridge data and full-market price structure.
2. **Backfill A-share rolling history** — scheduled/manual bounded history repair.
3. **Build SW taxonomy and company industry index** — scheduled refresh of Shenwan taxonomy and main-board company mapping.
4. **CI / Research contract CI** — validates code, data and low-risk production contracts.

## Low-risk runtime entry points

Load in this order:

1. `config/research_runtime_policy.json`
2. `config/research_pipeline_manifest.json`
3. the four authoritative Skills declared by the Manifest

The Manifest is the repository-data whitelist. The low-risk task must not scan arbitrary repository JSON files for extra research inputs.

## Authoritative low-risk repository data

The active production data surface is:

- `config/industry_scan_universe.json`
- `data/research/company_industry_index.json`
- `data/research/full_market_price_structure.json`
- `data/research/industry_state.json`
- `data/latest.json`
- `data/health.json`
- `data/history_shards/*.json`

Other market-maintenance files may exist for ingestion, repair or other workflows, but they are not low-risk research inputs unless the Manifest explicitly declares them.

## Persistence rule

`data/research/industry_state.json` is the only cross-run fundamental research memory. Company sets, profit chains, valuations, `reasonable_buy_range`, left-value assessments, left-turn assessments, Near-miss rankings and published leaderboards are generated fresh on every run and are not persisted as a candidate pool or formal-run state.

`research_state.json`, versioned/shadow research states and legacy `data/research/v2/*` outputs are forbidden as production runtime inputs.

## Public evidence layer

Current company filings, exchange disclosures, official statistics, commodity/industry data and other credible public evidence remain required for formal research. They are consumed for the current run and do not become persistent candidate/opportunity pools.
