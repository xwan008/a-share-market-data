# Low-risk research runtime data

This directory contains only current-runtime artifacts:
- `full_market_price_structure.json`: mechanical full-market timing snapshot.
- `research_state.json`: the only persisted Prompt research result; it may be absent when no valid current-schema run exists.

`research_state.json` may contain the current weekly profitability baseline used for daily incremental industry scans. That baseline is market-state memory only: it is not a weekly opportunity list, candidate pool, company pool, ranking or preselected answer set.

Public fundamental/industry evidence is researched at run time. No independent weekly pool, candidate cache, T2 cache or duplicated valuation output may be persisted. `research_state.manifest_schema` must equal the current Manifest schema.
