from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "data/research/pipeline/common_qualification_pool.json"
POLICY = ROOT / "config/t2_representative_policy.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_chain_audit(name: str, audit: dict, errors: list[str], conditional: bool = False) -> None:
    for tag, row in audit.items():
        cap = int(row.get("representative_cap", -1))
        selected = int(row.get("selected_count", -1))
        weekly = set(row.get("weekly_deep_review_selected_codes") or [])
        nonweekly = set(row.get("selected_nonweekly_codes") or [])
        selected_codes = weekly | nonweekly
        if len(selected_codes) != selected:
            errors.append(f"{name}:{tag}:selected_count_mismatch")
        if selected > cap:
            errors.append(f"{name}:{tag}:cap_violation:{selected}>{cap}")
        if conditional and cap > 1:
            errors.append(f"{name}:{tag}:conditional_cap_gt_1:{cap}")
        expected_mode = "conditional_t1" if conditional else "direct_t2"
        if row.get("recall_mode") != expected_mode:
            errors.append(f"{name}:{tag}:bad_recall_mode:{row.get('recall_mode')}")
        deferred_codes = set(row.get("deferred_codes") or [])
        if selected_codes & deferred_codes:
            errors.append(f"{name}:{tag}:selected_deferred_overlap")
        ranked = set(row.get("ranked_all_codes") or [])
        if selected_codes | deferred_codes != ranked:
            errors.append(f"{name}:{tag}:ranked_partition_mismatch")


def main() -> int:
    pool = load(POOL)
    policy = load(POLICY)
    errors: list[str] = []

    if pool.get("schema_version") != 3:
        errors.append(f"schema_version:{pool.get('schema_version')}!=3")

    arithmetic = pool.get("arithmetic") or {}
    recall_count = int(arithmetic.get("recall_unique_count", -1))
    weekly_count = int(arithmetic.get("weekly_pool_effective_count", -1))
    overlap = int(arithmetic.get("overlap_count", -1))
    merged = int(arithmetic.get("merged_pre_gate_count", -1))
    earnings_removed = int(arithmetic.get("future_earnings_gate_removals", -1))
    earnings_passed = int(arithmetic.get("future_earnings_gate_pass_count", -1))
    deferred = int(arithmetic.get("representative_selection_deferrals", -1))
    common_count = int(arithmetic.get("common_qualification_pool_count", -1))
    if recall_count + weekly_count - overlap != merged:
        errors.append("recall_merge_reconciliation")
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
        if row.get("conditional_t1_tags") and not row.get("t2_tags") and row.get("gate_mode") not in {"conditional_t1", "weekly_deep_review"}:
            errors.append(f"{code}:conditional_t1_common_without_strict_gate")
    for code, row in gate.items():
        if row.get("final_pool_status") == "deferred" and code in common:
            errors.append(f"{code}:deferred_still_in_common")

    t2_audit = pool.get("t2_representative_selection") or {}
    t1_audit = pool.get("conditional_t1_representative_selection") or {}
    validate_chain_audit("t2", t2_audit, errors, conditional=False)
    validate_chain_audit("t1", t1_audit, errors, conditional=True)

    reverse = pool.get("unconfirmed_reverse_trigger_audit") or {}
    required_tags = set(pool.get("unconfirmed_review_required_tags") or [])
    derived_required = {tag for tag, row in reverse.items() if row.get("review_status") == "review_required"}
    if required_tags != derived_required:
        errors.append("reverse_trigger_required_tag_mismatch")
    for tag, row in reverse.items():
        if row.get("industry_status") != "unconfirmed":
            errors.append(f"{tag}:reverse_trigger_non_unconfirmed")
        if row.get("review_status") not in {"review_required", "no_trigger"}:
            errors.append(f"{tag}:bad_reverse_review_status")
        triggered = any(bool(x.get("triggered")) for x in row.get("trigger_companies", []))
        if triggered != (row.get("review_status") == "review_required"):
            errors.append(f"{tag}:reverse_trigger_status_mismatch")

    if pool.get("representative_policy_reviewed_at") != policy.get("reviewed_at"):
        errors.append("representative_policy_review_date_mismatch")
    if pool.get("representative_policy_schema_version") != policy.get("schema_version"):
        errors.append("representative_policy_schema_mismatch")

    print(json.dumps({
        "status": "PASS" if not errors else "FAIL",
        "common_pool_count": common_count,
        "representative_deferrals": deferred,
        "t2_chain_count": len(t2_audit),
        "conditional_t1_chain_count": len(t1_audit),
        "reverse_review_required": sorted(required_tags),
        "errors": errors[:50],
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
