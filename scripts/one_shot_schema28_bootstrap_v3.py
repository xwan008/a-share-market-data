from __future__ import annotations

import json
import requests
import one_shot_schema28_bootstrap as base


def fetch_report(report_date: str) -> dict[str, dict]:
    filters = [f"(REPORTDATE='{report_date}')", f"(REPORTDATE='{report_date} 00:00:00')"]
    for flt in filters:
        rows = []
        page = 1
        while True:
            params = {
                "reportName": "RPT_LICO_FN_CPD",
                "columns": "ALL",
                "filter": flt,
                "pageNumber": page,
                "pageSize": 500,
                "sortColumns": "SECURITY_CODE",
                "sortTypes": "1",
            }
            r = requests.get(base.REPORT_URL, params=params, headers=base.HEADERS, timeout=30)
            r.raise_for_status()
            payload = r.json()
            result = payload.get("result") or {}
            batch = result.get("data") or []
            rows.extend(batch)
            pages = int(result.get("pages") or 0)
            if not batch or page >= pages:
                break
            page += 1
        if rows:
            out = {}
            for row in rows:
                code = str(row.get("SECURITY_CODE") or row.get("SECURITY_CODE_1") or "").zfill(6)
                if len(code) == 6:
                    out[code] = row
            if out:
                return out
    raise RuntimeError(f"no_report_rows:{report_date}")


base.fetch_report = fetch_report
base.main()

state = json.loads(base.OUT.read_text(encoding="utf-8"))

# Contract shape: one auditable screen object per confirmed improving chain.
flat = state.get("company_light_screen") or {}
by_chain: dict[str, dict] = {}
for entry in flat.values():
    for chain_id in entry.get("source_chain_ids") or []:
        bucket = by_chain.setdefault(chain_id, {"screen_complete": True, "screened_companies": []})
        bucket["screened_companies"].append(entry)
for bucket in by_chain.values():
    bucket["screened_companies"].sort(key=lambda x: x["code"])
state["company_light_screen"] = by_chain

# Normalize extreme-deviation audit field name required by schema28 persisted-state contract.
for v in (state.get("valuations") or {}).values():
    audit = v.get("extreme_valuation_deviation_audit")
    if isinstance(audit, dict):
        if "passed" not in audit:
            audit["passed"] = bool(audit.get("audit_passed", False))

# Buy-point assessments are only defined for complete non-review valuations.
state["buy_point_assessments"] = {
    code: assessment
    for code, assessment in (state.get("buy_point_assessments") or {}).items()
    if not (state.get("valuations", {}).get(code) or {}).get("review_required", False)
}
state.setdefault("diagnostics", {}).setdefault("buy_point", {})["assessed_count"] = len(state["buy_point_assessments"])

base.OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "postprocess": "schema28_contract_shape_aligned",
    "screened_chain_objects": len(by_chain),
    "non_review_buy_point_assessments": len(state["buy_point_assessments"]),
    "current_opportunities": len(state.get("current_opportunities") or []),
}, ensure_ascii=False))
