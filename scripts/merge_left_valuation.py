from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'data/research/pipeline/common_qualification_pool.json'
FUND = ROOT / 'data/research/pipeline/fundamental_valuation.json'
CYCLE = ROOT / 'data/research/pipeline/cycle_valuation.json'
AUDIT = ROOT / 'data/research/pipeline/valuation_policy_audit.json'
OUT = ROOT / 'data/research/pipeline/left_valuation_scan.json'
TZ = ZoneInfo('Asia/Shanghai')


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding='utf-8'))


def main() -> int:
    common = load(COMMON)
    fund = load(FUND)
    cycle = load(CYCLE)
    audit = load(AUDIT)
    if audit.get('hard_gate', {}).get('status') != 'PASS':
        raise RuntimeError(f"valuation policy audit not PASS:{audit.get('hard_gate')}")
    common_codes = list(common.get('common_pool_codes', []))
    by_code = {}
    for source, payload in [('fundamental', fund), ('cycle', cycle)]:
        for row in payload.get('companies', []):
            code = str(row.get('code', '')).zfill(6)
            if code in by_code:
                raise RuntimeError(f'duplicate valuation code across engines:{code}')
            by_code[code] = {**row, 'left_engine': source}
    missing = sorted(set(common_codes) - set(by_code))
    extra = sorted(set(by_code) - set(common_codes))
    if missing or extra:
        raise RuntimeError(f'left valuation coverage mismatch missing={missing} extra={extra}')
    companies = [by_code[c] for c in common_codes]
    left = sorted({c for c in fund.get('left_set_codes', [])} | {c for c in cycle.get('left_set_codes', [])})
    payload = {
        'schema_version': 3,
        'generated_at': datetime.now(TZ).isoformat(),
        'common_pool_count': len(common_codes),
        'fundamental_count': len(fund.get('companies', [])),
        'cycle_count': len(cycle.get('companies', [])),
        'companies': companies,
        'left_set_codes': left,
        'upstream': {'fundamental_valuation': 'PASS', 'cycle_valuation': 'PASS', 'valuation_policy_audit': 'PASS'},
        'method_note': 'Left valuation is a strict union of mutually exclusive fundamental and cycle engines and is blocked unless the full valuation-policy coverage audit passes with unsupported_policy=0.'
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status':'ok','common':len(common_codes),'fundamental':payload['fundamental_count'],'cycle':payload['cycle_count'],'left':len(left)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
