from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "data" / "research" / "pipeline"
INDUSTRY_SCAN = PIPELINE / "industry_scan.json"
T2_RECALL = PIPELINE / "t2_company_recall.json"
WEEKLY_SCAN = PIPELINE / "weekly_opportunity_scan.json"
OUTPUT = PIPELINE / "run_state.json"


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"missing required pipeline artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    industry = load(INDUSTRY_SCAN)
    recall = load(T2_RECALL)
    weekly = load(WEEKLY_SCAN)

    industry_frozen_at = industry.get("industry_frozen_at")
    recall_industry_frozen_at = recall.get("industry_scan_frozen_at")
    t2_recall_frozen_at = recall.get("t2_recall_frozen_at")
    weekly_t2_recall_frozen_at = weekly.get("t2_recall_frozen_at")
    weekly_pool_read_at = weekly.get("weekly_pool_read_at")

    missing = [
        name
        for name, value in {
            "industry_frozen_at": industry_frozen_at,
            "recall.industry_scan_frozen_at": recall_industry_frozen_at,
            "t2_recall_frozen_at": t2_recall_frozen_at,
            "weekly.t2_recall_frozen_at": weekly_t2_recall_frozen_at,
            "weekly_pool_read_at": weekly_pool_read_at,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"run-state source fields missing: {missing}")

    if recall_industry_frozen_at != industry_frozen_at:
        raise SystemExit("run-state mismatch: T2 recall does not point to current industry freeze")
    if weekly_t2_recall_frozen_at != t2_recall_frozen_at:
        raise SystemExit("run-state mismatch: weekly scan does not point to current T2 recall freeze")

    state = {
        "schema_version": 1,
        "industry_frozen_at": industry_frozen_at,
        "t2_recall_frozen_at": t2_recall_frozen_at,
        "weekly_pool_read_at": weekly_pool_read_at,
        "source_artifacts": {
            "industry_scan": "data/research/pipeline/industry_scan.json",
            "t2_company_recall": "data/research/pipeline/t2_company_recall.json",
            "weekly_opportunity_scan": "data/research/pipeline/weekly_opportunity_scan.json",
        },
        "purpose": "Audit that the weekly opportunity pool was read only after industry and T2 recall were frozen.",
    }
    OUTPUT.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
