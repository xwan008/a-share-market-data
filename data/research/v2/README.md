# Low-risk research runtime data

This directory contains only current-runtime artifacts:
- `full_market_price_structure.json`: mechanical full-market timing snapshot.
- `research_state.json`: the only persisted Prompt research result; it may be absent when no valid current-schema run exists.

The current baseline follows a lean prosperity-first design: use a broad Prompt-based full-market search to discover only the industries/themes with recent real-economy prosperity or profitability improvement, then map those directions through the SW taxonomy and perform evidence-based profitability verification only on the relevant level-3 industries. Level-1 and level-2 industries are routing taxonomy, not a persistent prosperity status matrix.

Weekly baseline memory contains only selected prosperity directions plus verified level-3 profitability states. Daily runs search for incremental new evidence and update only affected directions/chains. Previous companies, valuations, opportunities and near-miss rankings may not seed a new company discovery run.

Public fundamental/industry evidence is researched at run time. No independent weekly pool, candidate cache, T2 cache or duplicated valuation output may be persisted. `research_state.manifest_schema` must equal the current Manifest schema.
