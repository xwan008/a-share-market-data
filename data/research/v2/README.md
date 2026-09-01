# Low-risk research runtime data

This directory contains only current-runtime artifacts:
- `full_market_price_structure.json`: mechanical full-market timing snapshot.
- `research_state.json`: the only persisted Prompt research result; it may be absent when no valid current-schema run exists.

The current research baseline is prosperity-first: first scan all 31 level-1 and 134 level-2 SW industries for recent real-economy profitability/prosperity changes, then fully expand only the selected prosperity directions into their level-3 industries for evidence-based profitability verification. Unselected level-3 nodes remain taxonomically routed but are not required to receive a full profitability review each run.

The retained baseline is market-state memory only. It is not a weekly opportunity list, candidate pool, company pool, ranking, or preselected answer set. Previous companies, valuations and opportunities may not seed a new discovery run.

Public fundamental/industry evidence is researched at run time. No independent weekly pool, candidate cache, T2 cache or duplicated valuation output may be persisted. `research_state.manifest_schema` must equal the current Manifest schema.
