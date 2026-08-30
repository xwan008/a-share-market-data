from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "data/research/pipeline/common_qualification_pool.json"
POLICY = ROOT / "config/t2_representative_policy.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    pool = load(POOL)
    policy = load(POLICY)
    errors: list[str] = []

    if pool.get("schema_version") != 2:
        errors.append(f"schema_version:{pool.get('schema_version')}!=2")

    arithmetic = pool.get("arithmetic") or {}
    merged = int(arithmetic.get("merged_pre_gate_count", -1))
    earnings_removed = int(arithmetic.get("future_earnings_gate_removals", -1))
    earnings_passed = int(arithmetic.get("future_earnings_gate_pass_count", -1))
    deferred = int(arithmetic.get("representative_selection_deferrals", -1))
    common_count = int(arithmetic.get("common_qualification_pool_count", -1))
    if merged - earnings_removed != earnings_passed:
        errors.append("earnings_gate_reconciliation")
    if earnings_passed - deferred != common_count:
        errors.append("representative_reconciliation")

    common = set(pool.get("common_pool_codes") or [])
    if len(common) != common_count:
        errors.append(f"common_count:{len(common)}!={common_count}")

    gate = pool.get("future_earnings_gate") or {}
    for code in common:
        row = gate.get(code) or {}
        if row.get("gate_status") != "pass" or row.get("final_pool_status") != "pass":
            errors.append(f"{code}:common_without_final_pass")
    for code, row in gate.items():
        if row.get("final_pool_status") == "deferred" and code in common:
            errors.append(f"{code}:deferred_still_in_common")

    chain_audit = pool.get("t2_representative_selection") or {}
    for tag, row in chain_audit.items():
        cap = int(row.get("representative_cap", -1))
        selected = int(row.get("selected_count", -1))
        weekly = row.get("weekly_deep_review_selected_codes") or []
        selected_codes = set(weekly) | set(row.get("selected_t2_only_codes") or [])
        if len(selected_codes) != selected:
            errors.append(f"{tag}:selected_count_mismatch")
        if selected > cap:
            errors.append(f"{tag}:cap_violation:{selected}>{cap}")
        deferred_codes = set(row.get("deferred_codes") or [])
        if selected_codes & deferred_codes:
            errors.append(f"{tag}:selected_deferred_overlap")
        ranked = set(row.get("ranked_all_codes") or [])
        if selected_codes | deferred_codes != ranked:
            errors.append(f"{tag}:ranked_partition_mismatch")

    if pool.get("t2_representative_policy_reviewed_at") != policy.get("reviewed_at"):
        errors.append("representative_policy_review_date_mismatch")
    if pool.get("t2_representative_policy_schema_version") != policy.get("schema_version"):
        errors.append("representative_policy_schema_mismatch")

    print(json.dumps({
        "status": "PASS" if not errors else "FAIL",
        "common_pool_count": common_count,
        "representative_deferrals": deferred,
        "t2_chain_count": len(chain_audit),
        "errors": errors[:50],
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
