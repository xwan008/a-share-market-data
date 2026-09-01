# Research Data Layout

The low-risk research pipeline uses a stable production contract and does not use numeric research schema versions or shadow mode.

Authoritative research files:

- `company_industry_index.json` — mechanical company-to-SW-industry mapping.
- `full_market_price_structure.json` — latest full-market mechanical price-structure snapshot.
- `industry_state.json` — compact cross-run Level-3 profitability baseline; the only cross-run fundamental memory.
- `research_state.json` — latest valid complete formal research run.

Rules:

1. `industry_state.json` is refreshed only by valid research: weekly deep baseline refresh plus daily evidence-triggered Level-3 updates. Prompt discovery itself remains full-market on every run.
2. `research_state.json` is replaced only after Data Gate and Completion Gate both pass.
3. Failed, stale, or incomplete runs must not overwrite the previous valid state.
4. Candidate pools, opportunity pools, Near-miss pools, weekly Top lists, and standalone valuation caches are forbidden.
5. Legacy `data/research/v2/*` files are removed and are not runtime inputs.
