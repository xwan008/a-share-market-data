from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from math import isfinite
from typing import Any


@dataclass
class ValidationResult:
    confidence: str
    ok: bool
    warnings: list[str]
    source_prices: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def validate_price(
    *,
    primary_price: Any,
    secondary_price: Any | None,
    max_diff_pct: float = 0.2,
) -> ValidationResult:
    warnings: list[str] = []
    primary = _num(primary_price)
    secondary = _num(secondary_price)

    if primary is None or primary <= 0:
        return ValidationResult("invalid", False, ["primary_price_invalid"], {})

    source_prices = {"primary": primary}
    if secondary is None or secondary <= 0:
        warnings.append("secondary_source_unavailable")
        return ValidationResult("medium", True, warnings, source_prices)

    source_prices["secondary"] = secondary
    diff_pct = abs(primary - secondary) / primary * 100
    if diff_pct <= max_diff_pct:
        return ValidationResult("high", True, warnings, source_prices)

    warnings.append(f"source_price_diff_pct={diff_pct:.3f}")
    return ValidationResult("invalid", False, warnings, source_prices)


def validate_quote_fields(quote: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in ("price", "prev_close"):
        value = _num(quote.get(key))
        if value is None or value <= 0:
            warnings.append(f"{key}_invalid")

    price = _num(quote.get("price"))
    prev_close = _num(quote.get("prev_close"))
    pct = _num(quote.get("change_pct"))
    if price and prev_close and pct is not None:
        derived = (price / prev_close - 1) * 100
        if abs(derived - pct) > 0.5:
            warnings.append("change_pct_inconsistent")

    return warnings


def parse_quote_time(date_value: Any, time_value: Any, tz_suffix: str = "+08:00") -> str | None:
    if not date_value:
        return None
    date_text = str(date_value).replace("/", "-").strip()
    time_text = str(time_value or "15:00:00").strip()
    if len(time_text) == 5:
        time_text += ":00"
    try:
        dt = datetime.fromisoformat(f"{date_text}T{time_text}{tz_suffix}")
    except ValueError:
        return None
    return dt.isoformat()
