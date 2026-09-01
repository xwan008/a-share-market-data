from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import median

# Reuse the proven mechanical calculations only. The legacy module's main/output
# contract is intentionally NOT called; production output is defined here.
import build_v2_full_market_price_structure as engine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/full_market_price_structure.json"


def main():
    latest = engine.load(engine.LATEST, {})
    stocks = latest.get("stocks", {})
    reference_date = str(latest.get("trade_date") or "")

    base = {}
    market_returns = []
    for code, quote in stocks.items():
        code = str(code).zfill(6)
        row = engine.base_metrics(
            code,
            (quote or {}).get("name") or code,
            engine.rows_for(code),
            quote or {},
            reference_date,
        )
        base[code] = row
        if row.get("data_status") == "verified" and isinstance(row.get("raw_return_20d"), (int, float)):
            market_returns.append(row["raw_return_20d"])

    market_ret20 = median(market_returns) if market_returns else 0.0
    results = {code: engine.classify(row, market_ret20) for code, row in base.items()}
    candidates = sorted(
        code
        for code, row in results.items()
        if row.get("low_risk_eligible")
        and row.get("structure_type") in {"trend_continuation", "breakout", "pullback"}
        and row.get("chase_risk") != "high"
    )
    unavailable = sorted(code for code, row in results.items() if row.get("data_status") != "verified")

    counts = {}
    risk_count = 0
    for row in results.values():
        counts[row.get("structure_type")] = counts.get(row.get("structure_type"), 0) + 1
        risk_count += int(bool(row.get("risk_warning")))

    payload = {
        "contract_id": "a-share-low-risk-price-structure",
        "generated_at": datetime.now(engine.TZ).isoformat(),
        "reference_trade_date": reference_date,
        "universe_source": "all_mainboard_codes_from_data/latest.json",
        "universe_count": len(stocks),
        "verified_count": len(stocks) - len(unavailable),
        "unavailable_count": len(unavailable),
        "risk_warning_scanned_count": risk_count,
        "market_median_return_20d_pct": round(market_ret20 * 100, 2),
        "structure_type_counts": counts,
        "right_candidate_codes": candidates,
        "unavailable_codes": unavailable,
        "companies": results,
        "method_note": (
            "Full mainboard mechanical scan independent from fundamentals. "
            "Breakouts require price, volume and close confirmation; pullbacks "
            "require relative strength not materially below market."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "reference_trade_date": reference_date,
                "universe": len(stocks),
                "verified": payload["verified_count"],
                "right_candidates": len(candidates),
                "types": counts,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
