#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "industry_evidence_contract.json"
EVIDENCE_PATH = ROOT / "data" / "research" / "industry_evidence.json"
GATE_PATH = ROOT / "data" / "research" / "evidence_gate.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(mode: str):
    contract = read_json(CONTRACT_PATH)
    evidence = read_json(EVIDENCE_PATH)

    expected = int(contract["required_level1_count"])
    level1 = evidence.get("level1") or {}
    required_slots = [
        key for key, cfg in (contract.get("evidence_slots") or {}).items()
        if cfg.get("required")
    ]

    deficiencies = []
    complete = 0
    partial = 0
    missing = 0

    for code, row in sorted(level1.items()):
        slot_freshness = row.get("required_slot_freshness") or {}
        missing_slots = []
        stale_or_unknown_slots = []
        for slot in required_slots:
            items = (row.get("slots") or {}).get(slot) or []
            if not items:
                missing_slots.append(slot)
            elif not slot_freshness.get(slot):
                stale_or_unknown_slots.append(slot)
        status = row.get("evidence_status")
        if status == "complete":
            complete += 1
        elif status == "partial":
            partial += 1
        else:
            missing += 1

        if missing_slots or stale_or_unknown_slots:
            deficiencies.append({
                "code": code,
                "name": row.get("name"),
                "missing_slots": missing_slots,
                "stale_or_unknown_slots": stale_or_unknown_slots,
            })

    shape_valid = (
        evidence.get("contract_id") == "a-share-industry-evidence"
        and len(level1) == expected
        and (evidence.get("universe") or {}).get("actual_level1_count") == expected
    )
    strict_pass = bool(shape_valid and complete == expected and not deficiencies)

    gate = {
        "contract_id": "a-share-industry-evidence-gate",
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "reference_trade_date": evidence.get("reference_trade_date"),
        "shape_valid": shape_valid,
        "level1_expected": expected,
        "level1_accounted": len(level1),
        "complete": complete,
        "partial": partial,
        "missing": missing,
        "strict_pass": strict_pass,
        "decision_layer_ready": strict_pass,
        "shadow_run_allowed": mode == "shadow",
        "deficiencies": deficiencies,
        "semantics": (
            "In shadow mode this gate is diagnostic and must not replace the current formal production gate. "
            "Switch to strict only after machine evidence coverage is intentionally completed."
        ),
    }

    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_PATH.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mode": mode,
        "shape_valid": shape_valid,
        "complete": complete,
        "partial": partial,
        "missing": missing,
        "strict_pass": strict_pass,
    }, ensure_ascii=False))

    if not shape_valid:
        raise SystemExit(3)
    if mode == "strict" and not strict_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("shadow", "strict"), default="shadow")
    args = parser.parse_args()
    validate(args.mode)
