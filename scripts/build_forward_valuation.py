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


def load_spot_indicators(ak) -> dict[str, dict]:
    """One bulk request for market PB/dynamic PE. Missing fields are explicit data gaps, never guessed."""
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        return {}
    cols = list(df.columns)
    code_col = detect_col(cols, contains='代码')
    pb_col = detect_col(cols, exact='市净率') or detect_col(cols, contains='市净率')
    pe_col = detect_col(cols, exact='市盈率-动态') or detect_col(cols, contains='市盈率')
    if not code_col:
        return {}
    out = {}
    for _, r in df.iterrows():
        code = str(r.get(code_col, '')).zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue
        out[code] = {'pb': num(r.get(pb_col)) if pb_col else None, 'pe_dynamic': num(r.get(pe_col)) if pe_col else None}
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


def financial_policy(tags: list[str], policies: dict) -> tuple[dict | None, str | None]:
    s = ' '.join(tags)
    if '证券' in s:
        return policies.get('financial_policies', {}).get('broker'), 'broker'
    if '保险' in s:
        return policies.get('financial_policies', {}).get('insurance'), 'insurance'
    return None, None


def choose_pb_band(policy: dict, forward_roe: float) -> list[float] | None:
    for band in policy.get('roe_pb_bands', []):
        max_roe = num(band.get('roe_max'))
        rng = band.get('pb_range')
        if max_roe is not None and forward_roe <= max_roe and isinstance(rng, list) and len(rng) == 2:
            return [float(rng[0]), float(rng[1])]
    return None


def zone(price: float, fair_floor: float, policy: dict, default_band: dict) -> tuple[list[float], list[float], str]:
    safe_band = policy.get('safe_to_fair_floor') or default_band.get('safe_to_fair_floor') or [0.75, 0.88]
    reasonable_band = policy.get('reasonable_to_fair_floor') or default_band.get('reasonable_to_fair_floor') or [0.88, 1.0]
    safe = [fair_floor * safe_band[0], fair_floor * safe_band[1]]
    reasonable = [fair_floor * reasonable_band[0], fair_floor * reasonable_band[1]]
    if price <= safe[1]:
        conclusion = 'safe_buy_zone'
    elif price <= reasonable[1]:
        conclusion = 'reasonable_buy_zone'
    else:
        conclusion = 'above_buy_zone'
    return safe, reasonable, conclusion


def main() -> int:
    import akshare as ak

    common = load(COMMON)
    latest = load(LATEST)
    policies = load(POLICY)
    stocks = latest.get('stocks', {})
    consensus = load_consensus(ak)
    spot = load_spot_indicators(ak)
    year = datetime.now(TZ).year
    min_reports = int(policies.get('forecast_policy', {}).get('minimum_report_count', 3))
    default_band = policies.get('default_buy_band', {})

    companies = []
    left = []
    cycle_codes = []
    unsupported_policy_codes = []
    supported_policy_codes = []
    execution_counts = {'valid': 0, 'consensus_insufficient': 0, 'market_data_missing': 0, 'normalization_required': 0, 'unsupported_policy': 0}
    model_counts: dict[str, int] = {}

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
        fin_policy, fin_key = financial_policy(tags, policies)
        base_policy, policy_key = business_policy(tags, policies)
        policy = override or fin_policy or base_policy
        policy_kind = 'financial_pb_roe' if fin_policy and not override else 'forward_pe'
        model = None
        reason = None
        execution_state = None

        if override:
            model = override.get('valuation_model') or 'company_forward_pe'
        elif fin_policy:
            model = fin_policy.get('valuation_model') or f'{fin_key}_forward_pb_roe'
        elif base_policy:
            model = f'{policy_key}_forward_pe'

        if not policy:
            unsupported_policy_codes.append(code)
            execution_counts['unsupported_policy'] += 1
            execution_state = 'unsupported_policy'
            reason = 'No versioned PE/PB/EV policy mapped to this non-cycle company. This is a coverage failure, not an investability conclusion.'
        else:
            supported_policy_codes.append(code)

        c = consensus.get(code, {'report_count': 0, 'eps': {}})
        reports = int(c.get('report_count') or 0)
        eps_now = num(c.get('eps', {}).get(year))
        eps_next = num(c.get('eps', {}).get(year + 1))
        growth_next = ((eps_next / eps_now) - 1) * 100 if eps_now and eps_next else None
        market = spot.get(code, {})
        current_pb = num(market.get('pb'))
        market_dynamic_pe = num(market.get('pe_dynamic'))

        if execution_state is None and override and override.get('requires_normalized_earnings_bridge'):
            execution_state = 'normalization_required'
            execution_counts['normalization_required'] += 1
            reason = 'Company policy exists, but reported earnings contain material one-off/investment-income effects; a normalized recurring earnings bridge is required before formal valuation.'
        elif execution_state is None and (eps_now is None or reports < min_reports):
            execution_state = 'consensus_insufficient'
            execution_counts['consensus_insufficient'] += 1
            reason = f'Consensus insufficient: reports={reports}, eps_{year}={eps_now}; H1 annualization is diagnostic only.'
        elif execution_state is None and price is None:
            execution_state = 'market_data_missing'
            execution_counts['market_data_missing'] += 1
            reason = 'Current price missing.'

        if execution_state is not None:
            row = {
                'code': code, 'name': name, 'current_price': price,
                'valuation_status': 'unavailable', 'execution_state': execution_state,
                'policy_status': 'unsupported' if execution_state == 'unsupported_policy' else 'supported',
                'valuation_model': model or 'unsupported_business_model',
                'valuation_basis_unit': 'PB' if policy_kind == 'financial_pb_roe' else 'PE',
                'forecast_source': 'analyst_consensus' if eps_now else 'none', 'forecast_report_count': reports,
                'consensus_eps_current_year': round(eps_now, 4) if eps_now else None,
                'consensus_eps_next_year': round(eps_next, 4) if eps_next else None,
                'forward_earnings_basis': f'{year}/{year+1} consensus is primary; half-year annualization cannot create a formal anchor.',
                'reasonable_multiple_range': None, 'value_anchor_range': None,
                'reasonable_buy_range': None, 'safe_buy_range': None,
                'market_pb': round(current_pb, 4) if current_pb else None,
                'market_pe_dynamic': round(market_dynamic_pe, 4) if market_dynamic_pe else None,
                'key_sensitivities': ['future 1-2 quarter earnings', 'consensus revisions', 'valuation policy'],
                'invalidation_condition': gate.get('invalidation_condition') or 'future earnings bridge invalidated',
                'left_conclusion': 'unavailable', 'reason': reason,
            }
            companies.append(row)
            model_counts[row['valuation_model']] = model_counts.get(row['valuation_model'], 0) + 1
            continue

        if policy_kind == 'financial_pb_roe':
            if current_pb is None or current_pb <= 0:
                execution_counts['market_data_missing'] += 1
                row = {
                    'code': code, 'name': name, 'current_price': price, 'valuation_status': 'unavailable',
                    'execution_state': 'market_data_missing', 'policy_status': 'supported',
                    'valuation_model': model, 'valuation_basis_unit': 'PB',
                    'forecast_source': 'akshare.stock_profit_forecast_em', 'forecast_report_count': reports,
                    'consensus_eps_current_year': round(eps_now, 4),
                    'consensus_eps_next_year': round(eps_next, 4) if eps_next else None,
                    'forward_earnings_basis': 'Forward ROE-PB bridge requires market PB to infer latest BVPS; PB is missing or non-positive.',
                    'reasonable_multiple_range': None, 'value_anchor_range': None, 'reasonable_buy_range': None, 'safe_buy_range': None,
                    'key_sensitivities': ['forward ROE', 'market activity/investment return', 'book value quality'],
                    'invalidation_condition': gate.get('invalidation_condition') or 'forward ROE bridge invalidated',
                    'left_conclusion': 'unavailable', 'reason': 'market_pb_missing'
                }
                companies.append(row)
                model_counts[model] = model_counts.get(model, 0) + 1
                continue
            bvps = price / current_pb
            roe_now = eps_now / bvps
            roe_next = eps_next / bvps if eps_next else None
            forward_roe = roe_next if roe_next is not None else roe_now
            pb_range = choose_pb_band(policy, forward_roe)
            if not pb_range:
                raise RuntimeError(f'financial PB band missing for {code}: roe={forward_roe}')
            mult_lo, mult_hi = pb_range
            fair_lo, fair_hi = bvps * mult_lo, bvps * mult_hi
            safe, reasonable, conclusion = zone(price, fair_lo, policy, default_band)
            row = {
                'code': code, 'name': name, 'current_price': round(price, 3),
                'valuation_status': 'valid', 'execution_state': 'valid', 'policy_status': 'supported',
                'valuation_model': model, 'valuation_basis_unit': 'PB',
                'forecast_source': 'akshare.stock_profit_forecast_em+akshare.stock_zh_a_spot_em',
                'forecast_report_count': reports,
                'consensus_eps_current_year': round(eps_now, 4),
                'consensus_eps_next_year': round(eps_next, 4) if eps_next else None,
                'book_value_per_share_proxy': round(bvps, 4), 'market_pb': round(current_pb, 4),
                'forward_roe_current_year': round(roe_now, 4),
                'forward_roe_next_year': round(roe_next, 4) if roe_next is not None else None,
                'market_pe_dynamic': round(market_dynamic_pe, 4) if market_dynamic_pe else None,
                'market_forward_pe_current_year': round(price / eps_now, 2),
                'market_forward_pe_next_year': round(price / eps_next, 2) if eps_next else None,
                'forward_earnings_basis': f'BVPS proxy={bvps:.4f} from market PB; {year}/{year+1} consensus EPS maps to forward ROE, then to a versioned PB band.',
                'reasonable_multiple_range': [mult_lo, mult_hi],
                'multiple_rationale': policy.get('rationale'),
                'value_anchor_range': [round(fair_lo, 2), round(fair_hi, 2)],
                'safe_buy_range': [round(safe[0], 2), round(safe[1], 2)],
                'reasonable_buy_range': [round(reasonable[0], 2), round(reasonable[1], 2)],
                'key_sensitivities': ['forward ROE', 'book value quality', 'market activity/investment return'],
                'invalidation_condition': gate.get('invalidation_condition') or 'forward ROE or book-value bridge deteriorates',
                'left_conclusion': conclusion,
            }
        else:
            multiple = policy.get('multiple_range')
            if not isinstance(multiple, list) or len(multiple) != 2:
                unsupported_policy_codes.append(code)
                execution_counts['unsupported_policy'] += 1
                companies.append({
                    'code': code, 'name': name, 'current_price': price, 'valuation_status': 'unavailable',
                    'execution_state': 'unsupported_policy', 'policy_status': 'unsupported',
                    'valuation_model': model or 'unsupported_business_model', 'valuation_basis_unit': 'PE',
                    'forecast_source': 'akshare.stock_profit_forecast_em', 'forecast_report_count': reports,
                    'forward_earnings_basis': 'Versioned multiple_range missing.', 'reasonable_multiple_range': None,
                    'value_anchor_range': None, 'safe_buy_range': None, 'reasonable_buy_range': None,
                    'key_sensitivities': ['valuation policy'], 'invalidation_condition': 'policy coverage repaired',
                    'left_conclusion': 'unavailable', 'reason': 'versioned_multiple_missing'
                })
                continue
            pe_lo, pe_hi = float(multiple[0]), float(multiple[1])
            fair_lo, fair_hi = eps_now * pe_lo, eps_now * pe_hi
            safe, reasonable, conclusion = zone(price, fair_lo, policy, default_band)
            row = {
                'code': code, 'name': name, 'current_price': round(price, 3),
                'valuation_status': 'valid', 'execution_state': 'valid', 'policy_status': 'supported',
                'valuation_model': model, 'valuation_basis_unit': 'PE',
                'forecast_source': 'akshare.stock_profit_forecast_em', 'forecast_report_count': reports,
                'consensus_eps_current_year': round(eps_now, 4),
                'consensus_eps_next_year': round(eps_next, 4) if eps_next else None,
                'next_year_eps_growth_pct': round(growth_next, 2) if growth_next is not None else None,
                'market_pe_dynamic': round(market_dynamic_pe, 4) if market_dynamic_pe else None,
                'market_forward_pe_current_year': round(price / eps_now, 2),
                'market_forward_pe_next_year': round(price / eps_next, 2) if eps_next else None,
                'forward_earnings_basis': f'{year} consensus EPS={eps_now:.4f}; {year+1} EPS={eps_next:.4f}' if eps_next else f'{year} consensus EPS={eps_now:.4f}; next-year EPS unavailable.',
                'reasonable_multiple_range': [pe_lo, pe_hi],
                'multiple_rationale': policy.get('rationale') or 'Versioned business valuation policy considering growth durability, business quality and cyclicality.',
                'value_anchor_range': [round(fair_lo, 2), round(fair_hi, 2)],
                'safe_buy_range': [round(safe[0], 2), round(safe[1], 2)],
                'reasonable_buy_range': [round(reasonable[0], 2), round(reasonable[1], 2)],
                'key_sensitivities': ['future 1-2 quarter earnings', 'consensus revisions', 'reasonable multiple'],
                'invalidation_condition': gate.get('invalidation_condition') or 'future earnings bridge invalidated',
                'left_conclusion': conclusion,
            }

        execution_counts['valid'] += 1
        model_counts[row['valuation_model']] = model_counts.get(row['valuation_model'], 0) + 1
        if row['left_conclusion'] in {'safe_buy_zone', 'reasonable_buy_zone'}:
            left.append(code)
        companies.append(row)

    # A policy gap is a pipeline defect, not a normal unavailable state.
    payload = {
        'schema_version': 3,
        'generated_at': datetime.now(TZ).isoformat(),
        'common_pool_count': len(common.get('common_pool_codes', [])),
        'fundamental_company_count': len(companies),
        'deferred_cycle_codes': sorted(cycle_codes),
        'policy_coverage': {
            'noncycle_count': len(companies),
            'supported_policy_count': len(set(supported_policy_codes)),
            'unsupported_policy_count': len(set(unsupported_policy_codes)),
            'supported_policy_codes': sorted(set(supported_policy_codes)),
            'unsupported_policy_codes': sorted(set(unsupported_policy_codes)),
            'execution_counts': execution_counts,
            'model_counts': dict(sorted(model_counts.items())),
        },
        'companies': companies,
        'left_set_codes': sorted(left),
        'method_note': 'All non-cycle candidates must map to a versioned valuation policy. PE companies use consensus forward EPS; brokers/insurers execute a Forward ROE-PB bridge. Data insufficiency and normalization needs remain explicit execution states, not missing-policy shortcuts.',
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'ok', 'fundamental': len(companies), 'cycle_deferred': len(cycle_codes), 'left': len(left), 'unsupported_policy': len(set(unsupported_policy_codes)), 'execution': execution_counts}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
