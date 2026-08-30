from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from company_index_fingerprint import company_index_fingerprint

ROOT = Path(__file__).resolve().parents[1]
T2 = ROOT / "data" / "research" / "pipeline" / "t2_company_recall.json"
RUN_STATE = ROOT / "data" / "research" / "pipeline" / "run_state.json"
INDEX = ROOT / "data" / "research" / "company_industry_index.json"


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    t2 = json.loads(T2.read_text(encoding="utf-8"))
    run_state = json.loads(RUN_STATE.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))

    if int(t2.get("schema_version") or 0) < 2:
        raise SystemExit("migration_requires_t2_schema_v2")
    if t2.get("company_index_fingerprint") != company_index_fingerprint(index):
        raise SystemExit("migration_refuses_company_index_content_mismatch")
    if t2.get("industry_scan_frozen_at") != run_state.get("industry_frozen_at"):
        raise SystemExit("migration_refuses_industry_provenance_mismatch")

    current = parse_iso(t2["t2_recall_frozen_at"])
    original = parse_iso(run_state["t2_recall_frozen_at"])
    weekly_read = parse_iso(run_state["weekly_pool_read_at"])

    if not (original <= weekly_read):
        raise SystemExit("run_state_stage_order_invalid")

    if current == original:
        print(json.dumps({"status": "already_repaired", "t2_recall_frozen_at": t2["t2_recall_frozen_at"]}, ensure_ascii=False))
        return 0

    # This migration is intentionally one-way and only repairs the known schema-v2
    # metadata migration accident: the semantic recall was unchanged, but its freeze
    # time was refreshed to after the already-frozen weekly read.
    if not (current > weekly_read):
        raise SystemExit("migration_refuses_unexpected_t2_freeze_relation")

    t2["t2_recall_frozen_at"] = run_state["t2_recall_frozen_at"]
    T2.write_text(json.dumps(t2, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "repaired",
        "from": current.isoformat(),
        "to": t2["t2_recall_frozen_at"],
        "weekly_pool_read_at": run_state["weekly_pool_read_at"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
