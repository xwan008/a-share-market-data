# Low-risk research runtime data

This directory intentionally contains only current-runtime artifacts.

- `full_market_price_structure.json`: mechanical full-market price-structure snapshot, rebuilt by the normal post-close market workflow.
- `research_state.json`: generated only by a valid 18:00 full research run. It may be absent when no current-schema baseline exists.

`research_state.manifest_schema` must equal `config/research_pipeline_manifest.json.schema_version`. Old-schema states are stale and must not be relabeled or reused as current research.

No legacy pipeline outputs, rankings, T2 recall caches, company buckets, weekly opportunity pools or duplicated valuation outputs belong here. Git history is the audit trail.
