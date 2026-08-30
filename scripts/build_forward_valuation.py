from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'data/research/pipeline/common_qualification_pool.json'
LATEST = ROOT / 'data/latest.json'
POLICY = ROOT / 'config/valuation_policy_registry.json'
OUT = ROOT / 'data/research/pipeline/fundamental_valuation.json'
TZ = ZoneInfo('Asia/Shanghai')

CYCLE_KEYS = ('铜矿资源', '电解铝', '动力煤', '氟化工', '氨纶')
FIN_KEYS = ('证券', '保险')
ONE_OFF_UNAVAILABLE = {
    '002156': 'H1归母利润受产业投资收益明显增厚，本轮未取得足够精确的扣非EPS/股本桥，不能形成正式价值锚。'
}


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def detect_col(columns, exact=None, contains=None):
    for c in columns:
        s = str(c)
        if exact and s == exact:
            return c
        if contains and contains in s:
            return c
    return None


def load_consensus(ak) -> dict[str, dict]:
    """Load Eastmoney analyst consensus. Parser is column-name tolerant across AKShare versions."""
    df = ak.stock_profit_forecast_em()
    cols = list(df.columns)
    code_col = detect_col(cols, contains='代码')
    report_col = detect_col(cols, contains='研报数') or detect_col(cols, contains='机构')
    eps_cols: dict[int, object] = {}
    for c in cols:
        m = re.search(r'(20\d{2}).*预测.*每股收益', str(c))
        if m:
            eps_cols[int(m.group(1))] = c
    if not code_col:
        raise RuntimeError(f'profit forecast code column not found: {cols}')
    out: dict[str, dict] = {}
    for _, r in df.iterrows():
        code = str(r.get(code_col, '')).zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue
        row = {'report_count': int(num(r.get(report_col)) or 0), 'eps': {}}
        for year, col in eps_cols.items():
            v = num(r.get(col))
            if v is not None and v > 0:
                row['eps'][year] = v
        out[code] = row
    return out


def business_policy(tags: list[str], policies: dict) -> tuple[dict | None, str | None]:
    s = ' '.join(tags)
    mapping = [
        ('船舶制造', 'shipbuilding'),
        ('重卡', 'heavy_truck'),
        ('CXO', 'cxo_cdmo'), ('CDMO', 'cxo_cdmo'),
        ('特高压', 'grid_equipment'), ('电网一次设备', 'grid_equipment'),
        ('AI服务器', 'ai_server'),
        ('高速光模块', 'optical'),
        ('PCB/CCL', 'pcb_ccl'),
    ]
    for needle, key in mapping:
        if needle in s:
            p = policies.get('business_policies', {}).get(key)
            if p:
                return p, key
    return None, None


def main() -> int:
    import akshare as ak

    common = load(COMMON)
    latest = load(LATEST)
    policies = load(POLICY)
    stocks = latest.get('stocks', {})
    consensus = load_consensus(ak)
    year = datetime.now(TZ).year
    min_reports = int(policies.get('forecast_policy', {}).get('minimum_report_count', 3))
    default_band = policies.get('default_buy_band', {})

    companies = []
    left = []
    cycle_codes = []

    for code in common.get('common_pool_codes', []):
        gate = common['future_earnings_gate'][code]
        tags = gate.get('t2_tags') or []
        tag_text = ' '.join(tags)
        if any(k in tag_text for k in CYCLE_KEYS):
            cycle_codes.append(code)
            continue

        name = gate.get('name') or (stocks.get(code) or {}).get('name') or code
        price = num((stocks.get(code) or {}).get('price'))
        override = policies.get('company_overrides', {}).get(code)
        base_policy, policy_key = business_policy(tags, policies)
        policy = override or base_policy
        reason = None

        if any(k in tag_text for k in FIN_KEYS):
            policy = None
            model = 'PB_ROE_bridge_required'
            reason = '金融公司需要独立PB-ROE/资本回报桥，本次PE引擎不得替代。'
        else:
            model = (override or {}).get('valuation_model') or (policy_key + '_forward_pe' if policy_key else None)

        if code in ONE_OFF_UNAVAILABLE:
            policy = None
            model = 'one_off_normalization_unavailable'
            reason = ONE_OFF_UNAVAILABLE[code]

        c = consensus.get(code, {'report_count': 0, 'eps': {}})
        reports = int(c.get('report_count') or 0)
        eps_now = num(c.get('eps', {}).get(year))
        eps_next = num(c.get('eps', {}).get(year + 1))
        growth_next = ((eps_next / eps_now) - 1) * 100 if eps_now and eps_next else None

        if not policy:
            status = 'unavailable'
            reason = reason or '缺少经版本化审核的业务估值政策，拒绝临时拍PE。'
        elif eps_now is None or reports < min_reports:
            status = 'unavailable'
            reason = f'机构一致预期不足：reports={reports}, eps_{year}={eps_now}; H1×2只能诊断，不能形成正式价值锚。'
        elif price is None:
            status = 'unavailable'
            reason = '当前价格缺失。'
        else:
            status = 'valid'

        if status != 'valid':
            companies.append({
                'code': code, 'name': name, 'current_price': price,
                'valuation_status': 'unavailable', 'valuation_model': model or 'unsupported_business_model',
                'forecast_source': 'analyst_consensus' if eps_now else 'none',
                'forecast_report_count': reports,
                'forward_earnings_basis': f'{year}机构一致预期EPS优先；一致预期不足时半年报简单年化仅作诊断，不形成正式价值锚。',
                'reasonable_multiple_range': None, 'value_anchor_range': None,
                'reasonable_buy_range': None, 'safe_buy_range': None,
                'key_sensitivities': ['未来1-2季度盈利兑现', '一致预期修正', '业务估值政策'],
                'invalidation_condition': gate.get('invalidation_condition') or '未来盈利桥失效',
                'left_conclusion': 'unavailable', 'reason': reason,
            })
            continue

        multiple = policy.get('multiple_range')
        pe_lo, pe_hi = float(multiple[0]), float(multiple[1])
        fair_lo, fair_hi = eps_now * pe_lo, eps_now * pe_hi
        safe_band = policy.get('safe_to_fair_floor') or default_band.get('safe_to_fair_floor') or [0.75, 0.88]
        reasonable_band = policy.get('reasonable_to_fair_floor') or default_band.get('reasonable_to_fair_floor') or [0.88, 1.0]
        safe = [fair_lo * safe_band[0], fair_lo * safe_band[1]]
        reasonable = [fair_lo * reasonable_band[0], fair_lo * reasonable_band[1]]
        if price <= safe[1]:
            conclusion = 'safe_buy_zone'
        elif price <= reasonable[1]:
            conclusion = 'reasonable_buy_zone'
        else:
            conclusion = 'above_buy_zone'

        row = {
            'code': code, 'name': name, 'current_price': round(price, 3),
            'valuation_status': 'valid', 'valuation_model': model,
            'forecast_source': 'akshare.stock_profit_forecast_em',
            'forecast_report_count': reports,
            'consensus_eps_current_year': round(eps_now, 4),
            'consensus_eps_next_year': round(eps_next, 4) if eps_next else None,
            'next_year_eps_growth_pct': round(growth_next, 2) if growth_next is not None else None,
            'forward_earnings_basis': f'{year}机构一致预期EPS={eps_now:.4f}; 正式Forward E直接采用外部一致预期而非半年报简单年化。',
            'reasonable_multiple_range': [pe_lo, pe_hi],
            'multiple_rationale': policy.get('rationale') or '版本化业务估值政策；结合增长持续性、业务质量与周期属性复核。',
            'value_anchor_range': [round(fair_lo, 2), round(fair_hi, 2)],
            'safe_buy_range': [round(safe[0], 2), round(safe[1], 2)],
            'reasonable_buy_range': [round(reasonable[0], 2), round(reasonable[1], 2)],
            'key_sensitivities': ['未来1-2季度盈利兑现', '机构一致预期修正', '合理估值区间'],
            'invalidation_condition': gate.get('invalidation_condition') or '未来盈利桥失效',
            'left_conclusion': conclusion,
        }
        if conclusion in {'safe_buy_zone', 'reasonable_buy_zone'}:
            left.append(code)
        companies.append(row)

    payload = {
        'schema_version': 2,
        'generated_at': datetime.now(TZ).isoformat(),
        'common_pool_count': len(common.get('common_pool_codes', [])),
        'fundamental_company_count': len(companies),
        'deferred_cycle_codes': sorted(cycle_codes),
        'companies': companies,
        'left_set_codes': sorted(left),
        'method_note': 'Formal non-cycle valuation prioritizes analyst consensus forward EPS; simple half-year annualization is diagnostic only. Cycle candidates are physically deferred to cycle_valuation.',
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'ok', 'fundamental': len(companies), 'cycle_deferred': len(cycle_codes), 'left': len(left)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
