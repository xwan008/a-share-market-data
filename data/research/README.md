# Research Data Layout

The low-risk research pipeline uses a stable production contract and does not use numeric research schema versions or shadow mode.

Authoritative research files:

- `company_industry_index.json` — mechanical company-to-SW-industry mapping.
- `full_market_price_structure.json` — latest full-market mechanical price-structure snapshot.
- `industry_state.json` — compact cross-run Level-3 profitability baseline; the only cross-run research memory.

There is intentionally **no persisted formal-run state file**. In particular, `research_state.json` is forbidden.

Rules:

1. `industry_state.json` is refreshed only by valid research: weekly deep baseline refresh plus daily evidence-triggered Level-3 updates. Prompt discovery itself remains full-market on every run.
2. Company sets, profit chains, valuations, `reasonable_buy_range`, left-value buy assessments, left-turn buy assessments, Near-miss rankings, and final leaderboards are generated fresh on every run and are not persisted across runs.
3. The formal output has two buy lists: `left_value_buyable_now` for prices already inside `reasonable_buy_range`, and `left_turn_buyable_now` for the subset that also has a confirmed left-side turn.
4. Price structure is not a hard gate for the left-value list. It is used to identify the left-turn subset and to expose structural risk.
5. Failed, stale, or incomplete runs must not mutate `industry_state.json` and must not publish a previous run as a fallback.
6. Candidate pools, opportunity pools, Near-miss pools, weekly Top lists, standalone valuation caches, and persisted formal-run states are forbidden.
7. Legacy `data/research/v2/*` files are removed and are not runtime inputs.
