from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'data/research/pipeline/common_qualification_pool.json'
FUND = ROOT / 'data/research/pipeline/fundamental_valuation.json'
CYCLE = ROOT / 'data/research/pipeline/cycle_valuation.json'
OUT = ROOT / 'data/research/pipeline/valuation_policy_audit.json'
TZ = ZoneInfo('Asia/Shanghai')


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding='utf-8'))


def main() -> int:
    common = load(COMMON)
    fund = load(FUND)
    cycle = load(CYCLE)
    common_codes = {str(x).zfill(6) for x in common.get('common_pool_codes', [])}
    fund_rows = {str(r.get('code')).zfill(6): r for r in fund.get('companies', [])}
    cycle_rows = {str(r.get('code')).zfill(6): r for r in cycle.get('companies', [])}
    all_rows = {**fund_rows, **cycle_rows}

    unsupported = sorted(code for code, r in fund_rows.items() if r.get('policy_status') == 'unsupported' or r.get('execution_state') == 'unsupported_policy')
    supported = sorted(code for code in fund_rows if code not in unsupported)
    financial = sorted(code for code, r in fund_rows.items() if r.get('valuation_basis_unit') == 'PB')
    pe = sorted(code for code, r in fund_rows.items() if r.get('valuation_basis_unit') == 'PE' and code not in unsupported)
    normalization = sorted(code for code, r in fund_rows.items() if r.get('execution_state') == 'normalization_required')
    consensus_insufficient = sorted(code for code, r in fund_rows.items() if r.get('execution_state') == 'consensus_insufficient')
    market_data_missing = sorted(code for code, r in fund_rows.items() if r.get('execution_state') == 'market_data_missing')
    valid_fund = sorted(code for code, r in fund_rows.items() if r.get('valuation_status') == 'valid')
    valid_cycle = sorted(code for code, r in cycle_rows.items() if r.get('valuation_status') == 'valid')
    cycle_unavailable = sorted(code for code, r in cycle_rows.items() if r.get('valuation_status') != 'valid')
    missing = sorted(common_codes - set(all_rows))
    extra = sorted(set(all_rows) - common_codes)

    payload = {
        'schema_version': 1,
        'generated_at': datetime.now(TZ).isoformat(),
        'common_pool_count': len(common_codes),
        'fundamental_count': len(fund_rows),
        'cycle_count': len(cycle_rows),
        'coverage_count': len(set(all_rows) & common_codes),
        'missing_codes': missing,
        'extra_codes': extra,
        'noncycle_policy_coverage': {
            'noncycle_count': len(fund_rows),
            'supported_policy_count': len(supported),
            'unsupported_policy_count': len(unsupported),
            'supported_policy_codes': supported,
            'unsupported_policy_codes': unsupported,
            'pe_policy_codes': pe,
            'financial_pb_roe_policy_codes': financial,
            'normalization_required_codes': normalization,
            'consensus_insufficient_codes': consensus_insufficient,
            'market_data_missing_codes': market_data_missing,
            'valid_valuation_codes': valid_fund,
        },
        'cycle_coverage': {
            'cycle_count': len(cycle_rows),
            'valid_codes': valid_cycle,
            'unavailable_codes': cycle_unavailable,
            'resource_cycle_codes': cycle.get('resource_cycle_codes', []),
        },
        'hard_gate': {
            'unsupported_policy_must_be_zero': True,
            'common_pool_must_be_fully_accounted': True,
            'status': 'PASS' if not unsupported and not missing and not extra else 'FAIL'
        }
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': payload['hard_gate']['status'], 'common': len(common_codes), 'fundamental': len(fund_rows), 'cycle': len(cycle_rows), 'unsupported_policy': len(unsupported), 'missing': len(missing)}, ensure_ascii=False))
    return 0 if payload['hard_gate']['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
