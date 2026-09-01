from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/industry_state.json"
LEGACY_COMMIT = "065e7727cba447159767eaaf67c32dc5a0f85dca"
LEGACY_PATH = "data/research/v2/research_state.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_legacy() -> dict:
    raw = subprocess.check_output(
        ["git", "show", f"{LEGACY_COMMIT}:{LEGACY_PATH}"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    return json.loads(raw)


def normalize_breadth(value):
    return "narrow" if value == "selective" else value


def migrate() -> dict:
    legacy = load_legacy()
    rows = legacy.get("level3_profitability_verification") or []
    if not rows:
        raise RuntimeError("legacy level3_profitability_verification is empty")

    level3 = {}
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        level3[code] = {
            "code": code,
            "name": row.get("name"),
            "trend": row.get("trend"),
            "strength": row.get("strength"),
            "breadth": normalize_breadth(row.get("breadth")),
            "confidence": row.get("confidence"),
            "evidence_basis": row.get("evidence_basis"),
            "leading_variables": row.get("leading_variables") or [],
            "profit_driver": row.get("profit_driver"),
            "falsifiers": row.get("falsifiers") or [],
            "last_verified_at": row.get("last_verified_at") or legacy.get("generated_at"),
            "linked_prosperity_directions": row.get("linked_prosperity_directions") or [],
            "company_count_with_paired_h1": row.get("company_count_with_paired_h1"),
            "core_earnings_pair_count": row.get("core_earnings_pair_count"),
            "core_improving_breadth": row.get("core_improving_breadth"),
            "aggregate_revenue_yoy": row.get("aggregate_revenue_yoy"),
            "aggregate_parent_profit_yoy": row.get("aggregate_parent_profit_yoy"),
        }

    return {
        "contract_id": "a-share-low-risk-production",
        "status": "valid",
        "baseline_trade_date": legacy.get("data_cutoff") or legacy.get("weekly_baseline_date"),
        "last_valid_baseline_date": legacy.get("weekly_baseline_date") or legacy.get("data_cutoff"),
        "generated_at": legacy.get("generated_at"),
        "migration": {
            "source_commit": LEGACY_COMMIT,
            "source_path": LEGACY_PATH,
            "scope": "level3_profitability_only",
            "legacy_company_valuation_buy_state_reused": False,
            "breadth_normalization": {"selective": "narrow"},
        },
        "level3_profitability": level3,
    }


def main():
    current = load_json(OUT)
    if current.get("status") == "valid" and current.get("level3_profitability"):
        print(json.dumps({
            "status": "noop",
            "reason": "valid_level3_state_already_exists",
            "level3_count": len(current["level3_profitability"]),
        }, ensure_ascii=False))
        return

    payload = migrate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "baseline_trade_date": payload["baseline_trade_date"],
        "level3_count": len(payload["level3_profitability"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
