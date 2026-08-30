from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/research/pipeline/fundamental_valuation.json'


def valid_range(v):
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and v[0] <= v[1]


def main() -> int:
    data = json.loads(OUT.read_text(encoding='utf-8'))
    errors: list[str] = []
    rows = {str(r.get('code')).zfill(6): r for r in data.get('companies', []) if isinstance(r, dict)}

    if int(data.get('schema_version') or 0) < 5:
        errors.append(f"fundamental_schema_too_old:{data.get('schema_version')}")

    for code, row in rows.items():
        if row.get('valuation_status') != 'valid' or row.get('valuation_basis_unit') != 'PE':
            continue
        theoretical = row.get('theoretical_business_multiple_range')
        low_risk = row.get('reasonable_multiple_range')
        business_fair = row.get('business_fair_value_range')
        anchor = row.get('value_anchor_range')
        safe = row.get('safe_buy_range')
        reasonable = row.get('reasonable_buy_range')
        if not valid_range(theoretical): errors.append(f'{code}:missing_theoretical_business_multiple_range')
        if not valid_range(low_risk): errors.append(f'{code}:missing_low_risk_multiple_range')
        if not valid_range(business_fair): errors.append(f'{code}:missing_business_fair_value_range')
        if not valid_range(anchor): errors.append(f'{code}:missing_low_risk_value_anchor_range')
        if not valid_range(safe): errors.append(f'{code}:missing_safe_buy_range')
        if not valid_range(reasonable): errors.append(f'{code}:missing_reasonable_buy_range')
        if not row.get('low_risk_pe_method'): errors.append(f'{code}:missing_low_risk_pe_method')
        if not isinstance(row.get('consensus_eps_current_year'), (int, float)) or row['consensus_eps_current_year'] <= 0:
            errors.append(f'{code}:missing_current_year_eps_anchor')
        if valid_range(theoretical) and valid_range(low_risk):
            if low_risk[0] > theoretical[0] + 1e-9 or low_risk[1] > theoretical[1] + 1e-9:
                errors.append(f'{code}:low_risk_pe_exceeds_theoretical:{low_risk}>{theoretical}')
        if valid_range(business_fair) and valid_range(anchor):
            if anchor[0] > business_fair[0] + 0.02 or anchor[1] > business_fair[1] + 0.02:
                errors.append(f'{code}:low_risk_anchor_exceeds_business_fair:{anchor}>{business_fair}')
        if valid_range(anchor) and valid_range(reasonable):
            if reasonable[1] > anchor[0] + 0.02:
                errors.append(f'{code}:reasonable_buy_above_low_risk_fair_floor:{reasonable}>{anchor}')
        if valid_range(safe) and valid_range(reasonable) and safe[1] > reasonable[1] + 1e-9:
            errors.append(f'{code}:safe_zone_above_reasonable_zone')

    # Regression locks: ranges are intentionally broad enough to allow small consensus EPS revisions,
    # but narrow enough to catch a return to the old industry-PE inflation bug.
    focus = {
        '002452': {'safe_upper_max': 11.2, 'reasonable_upper_max': 12.3},
        '002709': {'safe_upper_max': 36.0, 'reasonable_upper_max': 40.0},
        '600710': {'safe_upper_max': 10.8, 'reasonable_upper_max': 12.0},
        '603659': {'safe_upper_max': 24.5, 'reasonable_upper_max': 27.5},
    }
    for code, limits in focus.items():
        row = rows.get(code)
        if not row or row.get('valuation_status') != 'valid':
            errors.append(f'{code}:focus_company_not_valid')
            continue
        safe = row.get('safe_buy_range'); reasonable = row.get('reasonable_buy_range')
        if not valid_range(safe) or not valid_range(reasonable):
            errors.append(f'{code}:focus_ranges_missing')
            continue
        if safe[1] > limits['safe_upper_max']:
            errors.append(f"{code}:safe_upper_regressed:{safe[1]}>{limits['safe_upper_max']}")
        if reasonable[1] > limits['reasonable_upper_max']:
            errors.append(f"{code}:reasonable_upper_regressed:{reasonable[1]}>{limits['reasonable_upper_max']}")

    if errors:
        print(json.dumps({'status': 'FAIL', 'errors': errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({'status': 'PASS', 'valid_pe_rows': sum(1 for r in rows.values() if r.get('valuation_status') == 'valid' and r.get('valuation_basis_unit') == 'PE'), 'focus_codes': sorted(focus)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
