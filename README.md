# A-share Market Data + Low-risk Research Bridge

The repository keeps the A-share low-risk workflow small and auditable.

## Active workflows
1. **Update A-share market data** — weekdays 16:10/16:30 Asia/Shanghai; refreshes closed-session quotes/history/bridge and full-market price structure.
2. **Backfill A-share rolling history** — weekly Saturday or manual; repairs bounded history and summaries.
3. **Build SW taxonomy and company industry index** — weekly Sunday; refreshes Shenwan 2021 31/134/346 taxonomy and main-board company mapping.
4. **CI** — validates code/config/Skill contracts without writing market data.

## Low-risk rule sources
Load `research_runtime_policy.json` → current Manifest → four authoritative Skills. The Manifest owns machine contracts; detailed research discipline lives in Skills.

## Two source layers
**Persistent repository data** is limited to Manifest `authoritative_data`: SW taxonomy, company index, market snapshot/history, full-market price structure and current research state.

**Current public research evidence** is separate and is required for the 18:00 full study: company filings/announcements, exchange disclosures, official statistics, industry/commodity/price-spread/order/production data and other credible current evidence. The repository whitelist does not block this evidence layer.

Public evidence is consumed for the current run; it must not be converted into weekly pools, candidate pools, T2 registries or other cross-run research caches.

18:00 always starts from current full-market Coverage. Only the final structured Prompt result is persisted as `data/research/v2/research_state.json`. A state with a mismatched `manifest_schema` is stale.
