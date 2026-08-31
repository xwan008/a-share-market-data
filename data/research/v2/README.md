# Low-risk research runtime data

This directory contains only current-runtime artifacts:
- `full_market_price_structure.json`: mechanical full-market timing snapshot.
- `research_state.json`: the only persisted Prompt research result; it may be absent when no valid current-schema full run exists.

Public fundamental/industry evidence is researched at run time and is not persisted here as candidate pools, weekly pools, rankings, T2 caches or duplicated valuation outputs. `research_state.manifest_schema` must equal the current Manifest schema.
