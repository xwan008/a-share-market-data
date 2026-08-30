from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'data/research/pipeline/common_qualification_pool.json'
LATEST = ROOT / 'data/latest.json'
HEALTH = ROOT / 'data/health.json'
HISTORY_DIR = ROOT / 'data/history_shards'
POLICY = ROOT / 'config/cycle_valuation_policy.json'
REGIME = ROOT / 'config/cycle_regime_registry.json'
OUT = ROOT / 'data/research/pipeline/cycle_valuation.json'
TZ = ZoneInfo('Asia/Shanghai')
CYCLE_TAGS = ('nonferrous::铜矿资源', 'nonferrous::电解铝', 'coal::动力煤', 'chemicals::氟化工', 'chemicals::氨纶')
RESOURCE_TAGS = ('nonferrous::铜矿资源', 'nonferrous::电解铝')
MAX_ANCHOR_AGE_DAYS = 7


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def parse_day(v: object) -> date:
    return date.fromisoformat(str(v)[:10])


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError('empty percentile input')
    ordered = sorted(values)
    q = max(0.0, min(1.0, float(q)))
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def load_consensus(ak) -> dict[str, dict]:
    df = ak.stock_profit_forecast_em()
    cols = list(df.columns)
    code_col = next((c for c in cols if '代码' in str(c)), None)
    report_col = next((c for c in cols if '研报数' in str(c)), None)
    eps_cols = {}
    for c in cols:
        m = re.search(r'(20\d{2}).*预测.*每股收益', str(c))
        if m:
            eps_cols[int(m.group(1))] = c
    if code_col is None:
        raise RuntimeError(f'profit forecast code column not found: {cols}')
    out = {}
    for _, r in df.iterrows():
        code = str(r.get(code_col, '')).zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue
        out[code] = {
            'report_count': int(num(r.get(report_col)) or 0),
            'eps': {year: num(r.get(col)) for year, col in eps_cols.items() if num(r.get(col)) and num(r.get(col)) > 0},
        }
    return out


def load_spot(ak) -> dict[str, dict]:
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        return {}
    cols = list(df.columns)
    code_col = next((c for c in cols if '代码' in str(c)), None)
    pe_col = next((c for c in cols if str(c) == '市盈率-动态'), None) or next((c for c in cols if '市盈率' in str(c)), None)
    if code_col is None:
        return {}
    out = {}
    for _, r in df.iterrows():
        code = str(r.get(code_col, '')).zfill(6)
        if code.isdigit() and len(code) == 6:
            out[code] = {'pe_dynamic': num(r.get(pe_col)) if pe_col else None}
    return out


def fetch_anchor(ak, symbol: str, reference_trade_date: str, neutral_window_sessions: int, minimum_neutral_sessions: int) -> dict:
    df = ak.futures_zh_daily_sina(symbol=symbol)
    if df is None or df.empty:
        raise RuntimeError(f'empty futures series:{symbol}')
    close_col = next((c for c in df.columns if str(c).lower() == 'close'), None)
    date_col = next((c for c in df.columns if str(c).lower() == 'date'), None)
    if close_col is None or date_col is None:
        raise RuntimeError(f'required column missing:{symbol}:{list(df.columns)}')
    pairs = []
    for _, r in df.iterrows():
        v = num(r.get(close_col))
        if v is not None and v > 0:
            pairs.append((str(r.get(date_col))[:10], v))
    if len(pairs) < max(60, minimum_neutral_sessions):
        raise RuntimeError(f'insufficient_futures_history:{symbol}:{len(pairs)}')
    last_date = pairs[-1][0]
    age_days = (parse_day(reference_trade_date) - parse_day(last_date)).days
    if age_days < -1 or age_days > MAX_ANCHOR_AGE_DAYS:
        raise RuntimeError(f'stale_anchor:{symbol}:last_date={last_date}:reference={reference_trade_date}:age_days={age_days}')
    vals = [x[1] for x in pairs]
    current = vals[-1]
    ma20 = sum(vals[-20:]) / 20
    ma60 = sum(vals[-60:]) / 60
    high60 = max(vals[-60:])
    neutral_vals = vals[-min(neutral_window_sessions, len(vals)):]
    neutral_median = percentile(neutral_vals, 0.50)
    neutral_p40 = percentile(neutral_vals, 0.40)
    neutral_p60 = percentile(neutral_vals, 0.60)
    return {
        'symbol': symbol,
        'last_date': last_date,
        'age_days': age_days,
        'current': current,
        'ma20': ma20,
        'ma60': ma60,
        'current_to_ma20': current / ma20,
        'current_to_ma60': current / ma60,
        'drawdown_from_60d_high_pct': (current / high60 - 1) * 100,
        'trend_20_vs_60_pct': (ma20 / ma60 - 1) * 100,
        'neutral_window_sessions': len(neutral_vals),
        'neutral_price_median': neutral_median,
        'neutral_price_p40': neutral_p40,
        'neutral_price_p60': neutral_p60,
        'current_to_neutral': current / neutral_median,
    }


def load_market_price_anchor(code: str, market_policy: dict) -> dict | None:
    window = int(market_policy.get('window_sessions', 180))
    minimum = int(market_policy.get('minimum_sessions', 120))
    shard_len = int(market_policy.get('history_shard_key_length', 4))
    path = HISTORY_DIR / f'{code[:shard_len]}.json'
    if not path.exists():
        return None
    shard = load(path)
    stock = (shard.get('stocks') or {}).get(code) or {}
    history = stock.get('history') or []
    closes = [num(x.get('close')) for x in history[-window:] if isinstance(x, dict)]
    closes = [x for x in closes if x is not None and x > 0]
    if len(closes) < minimum:
        return None
    safe_p = market_policy.get('safe_percentiles', [0.15, 0.35])
    reasonable_p = market_policy.get('reasonable_percentiles', [0.35, 0.60])
    if not (isinstance(safe_p, list) and len(safe_p) == 2 and isinstance(reasonable_p, list) and len(reasonable_p) == 2):
        raise RuntimeError(f'invalid_market_price_anchor_percentiles:{market_policy}')
    ma60 = sum(closes[-60:]) / min(60, len(closes))
    return {
        'history_points': len(closes),
        'history_basis': stock.get('history_basis'),
        'last_history_date': str((history[-1] or {}).get('date') or '')[:10] if history else None,
        'low_180d': min(closes),
        'high_180d': max(closes),
        'median_180d': percentile(closes, 0.50),
        'ma60': ma60,
        'safe_percentile_band': [percentile(closes, float(safe_p[0])), percentile(closes, float(safe_p[1]))],
        'reasonable_percentile_band': [percentile(closes, float(reasonable_p[0])), percentile(closes, float(reasonable_p[1]))],
        'percentiles': {
            'p15': percentile(closes, 0.15),
            'p25': percentile(closes, 0.25),
            'p35': percentile(closes, 0.35),
            'p50': percentile(closes, 0.50),
            'p60': percentile(closes, 0.60),
        },
    }


def normalize_forward_eps(forward_eps: float, weighted_neutral_delta: float, sensitivity: float, neutral_policy: dict) -> tuple[float, float]:
    """Remove commodity windfall embedded in consensus before valuing a low-risk entry.

    Positive windfall means selling prices are above their neutral level and/or key input costs
    are below neutral. It can only reduce the normalized earnings base. Weak commodity conditions
    do not mechanically increase the low-risk earnings base.
    """
    windfall = max(0.0, weighted_neutral_delta)
    raw_factor = 1.0 / (1.0 + windfall * sensitivity)
    min_factor = float(neutral_policy.get('min_normalization_factor', 0.70))
    factor = max(min_factor, min(1.0, raw_factor))
    return forward_eps * factor, factor


def calibrate_low_risk_buy_bands(fair_floor: float, market_anchor: dict | None, policy: dict, market_policy: dict) -> tuple[list[float], list[float], list[float], str]:
    safe_band = policy.get('safe_to_fair_floor', [0.75, 0.88])
    reasonable_band = policy.get('reasonable_to_fair_floor', [0.88, 1.0])
    valuation_safe = [fair_floor * float(safe_band[0]), fair_floor * float(safe_band[1])]
    valuation_reasonable = [fair_floor * float(reasonable_band[0]), fair_floor * float(reasonable_band[1])]
    if not market_anchor:
        return valuation_safe, valuation_reasonable, [valuation_safe[0], valuation_reasonable[1]], 'valuation_only_history_unavailable'

    macro_haircut = float(market_policy.get('macro_uncertainty_haircut', 0.95))
    max_reasonable_to_ma60 = float(market_policy.get('max_reasonable_to_ma60', 1.06))
    fair_ceiling = fair_floor * macro_haircut
    ma60_ceiling = float(market_anchor['ma60']) * max_reasonable_to_ma60
    reasonable_ceiling = min(fair_ceiling, ma60_ceiling)

    market_safe = [float(x) for x in market_anchor['safe_percentile_band']]
    market_reasonable = [float(x) for x in market_anchor['reasonable_percentile_band']]
    market_reasonable_upper = min(market_reasonable[1], reasonable_ceiling)

    # If the normalized fundamental ceiling has fallen below the historical p35 area, valuation
    # must dominate rather than forcing an artificial historical band.
    if market_reasonable_upper < market_reasonable[0]:
        return valuation_safe, valuation_reasonable, [valuation_safe[0], valuation_reasonable[1]], 'valuation_dominant_below_market_p35'

    safe_upper = min(market_safe[1], market_reasonable_upper)
    safe_lower = min(market_safe[0], safe_upper)
    reasonable_lower = max(safe_upper, market_reasonable[0])
    reasonable_upper = max(reasonable_lower, market_reasonable_upper)
    safe = [safe_lower, safe_upper]
    reasonable = [reasonable_lower, reasonable_upper]
    value_anchor = [safe_lower, reasonable_upper]
    return safe, reasonable, value_anchor, 'normalized_fundamental_plus_180d_market_calibration'


def policy_for(tags: list[str], code: str, cfg: dict) -> tuple[str | None, dict | None]:
    matched = next((t for t in tags if t in CYCLE_TAGS), None)
    if not matched:
        return None, None
    base = dict(cfg.get('subchain_policies', {}).get(matched, {}))
    override = cfg.get('company_overrides', {}).get(code, {})
    if override:
        base.update(override)
    return matched, base or None


def regime_for(tag: str, code: str, registry: dict) -> dict | None:
    base = dict(registry.get('subchains', {}).get(tag, {}))
    override = registry.get('company_overrides', {}).get(code, {})
    if override:
        base.update(override)
    return base or None


def calendar_forward_eps(eps_now: float, eps_next: float, now: datetime) -> tuple[float, float, float]:
    """Approximate forward-12m EPS: remaining part of current FY + matching part of next FY."""
    current_weight = max(0.0, min(1.0, (12 - now.month) / 12.0))
    next_weight = 1.0 - current_weight
    return eps_now * current_weight + eps_next * next_weight, current_weight, next_weight


def main() -> int:
    import akshare as ak

    common = load(COMMON)
    latest = load(LATEST)
    health = load(HEALTH)
    cfg = load(POLICY)
    regime_registry = load(REGIME)
    reference_trade_date = str(health.get('trade_date') or '')[:10]
    if not reference_trade_date:
        raise RuntimeError('missing health trade_date for commodity freshness validation')
    review_day = parse_day(regime_registry.get('reviewed_at'))
    regime_age_days = (parse_day(reference_trade_date) - review_day).days
    max_regime_age = int(regime_registry.get('max_review_age_days', 45))

    stocks = latest.get('stocks', {})
    consensus = load_consensus(ak)
    spot = load_spot(ak)
    now = datetime.now(TZ)
    year = now.year
    min_reports = int(cfg.get('forward_earnings_policy', {}).get('minimum_report_count', 3))
    require_next_resource = bool(cfg.get('forward_earnings_policy', {}).get('require_next_year_eps_for_resource', True))
    max_short_effect = float(cfg.get('short_term_anchor_policy', {}).get('max_absolute_effect_on_eps', 0.05))
    neutral_policy = cfg.get('neutral_commodity_policy', {})
    neutral_window_sessions = int(neutral_policy.get('window_sessions', 252))
    minimum_neutral_sessions = int(neutral_policy.get('minimum_sessions', 180))
    market_policy = cfg.get('low_risk_price_calibration', {})

    anchor_cache = {}
    anchor_errors = {}
    companies = []
    left = []
    cycle_codes = []

    for code in common.get('common_pool_codes', []):
        gate = common['future_earnings_gate'][code]
        tags = gate.get('t2_tags') or []
        matched_tag, policy = policy_for(tags, code, cfg)
        if not matched_tag:
            continue
        cycle_codes.append(code)
        name = gate.get('name') or (stocks.get(code) or {}).get('name') or code
        price = num((stocks.get(code) or {}).get('price'))
        is_resource = matched_tag in RESOURCE_TAGS
        regime = regime_for(matched_tag, code, regime_registry) if is_resource else None

        if not policy or not policy.get('anchors'):
            companies.append({
                'code': code, 'name': name, 'cycle_tag': matched_tag, 'current_price': price,
                'valuation_status': 'unavailable', 'valuation_model': 'manual_spread_anchor_required',
                'execution_state': 'machine_anchor_policy_missing',
                'forward_earnings_basis': 'This subchain has no machine-verifiable commodity/spread anchor; TTM PE is not an allowed substitute.',
                'commodity_anchors': [], 'reasonable_multiple_range': None, 'value_anchor_range': None,
                'safe_buy_range': None, 'reasonable_buy_range': None, 'left_conclusion': 'unavailable',
                'reason': 'cycle_policy_missing_machine_readable_anchor',
                'invalidation_condition': gate.get('invalidation_condition') or 'cycle earnings bridge invalidated',
            })
            continue

        if is_resource and (regime is None or regime_age_days > max_regime_age or regime_age_days < -7):
            companies.append({
                'code': code, 'name': name, 'cycle_tag': matched_tag, 'current_price': price,
                'valuation_status': 'unavailable', 'valuation_model': 'forward_cycle_regime_required',
                'execution_state': 'cycle_regime_missing_or_stale',
                'forward_earnings_basis': 'Resource valuation requires a reviewed 6-18m supply-demand regime before applying a multiple.',
                'commodity_anchors': [], 'reasonable_multiple_range': None, 'value_anchor_range': None,
                'safe_buy_range': None, 'reasonable_buy_range': None, 'left_conclusion': 'unavailable',
                'reason': f'cycle_regime_missing_or_stale:age_days={regime_age_days}:max={max_regime_age}',
                'invalidation_condition': gate.get('invalidation_condition') or 'cycle regime invalidated',
            })
            continue

        anchors = []
        weighted_short_delta = 0.0
        weighted_neutral_delta = 0.0
        missing = []
        for a in policy.get('anchors', []):
            symbol = a['symbol']
            if symbol not in anchor_cache and symbol not in anchor_errors:
                try:
                    anchor_cache[symbol] = fetch_anchor(ak, symbol, reference_trade_date, neutral_window_sessions, minimum_neutral_sessions)
                except Exception as exc:
                    anchor_errors[symbol] = f'{type(exc).__name__}:{exc}'
            if symbol in anchor_errors:
                missing.append(symbol)
                continue
            m = anchor_cache[symbol]
            weight = float(a.get('weight', 1.0))
            direction = float(a.get('direction', 1.0))
            weighted_short_delta += weight * (m['current_to_ma60'] - 1.0) * direction
            weighted_neutral_delta += weight * (m['current_to_neutral'] - 1.0) * direction
            anchors.append({**m, 'weight': weight, 'direction': direction})

        c = consensus.get(code, {'report_count': 0, 'eps': {}})
        eps_now = num(c.get('eps', {}).get(year))
        eps_next = num(c.get('eps', {}).get(year + 1))
        reports = int(c.get('report_count') or 0)
        consensus_missing = eps_now is None or reports < min_reports or (is_resource and require_next_resource and eps_next is None)
        if missing or consensus_missing or price is None:
            reason_parts = []
            if missing:
                reason_parts.append(f'commodity_anchor_fetch_failed:{missing}')
            if consensus_missing:
                reason_parts.append(f'forward_consensus_insufficient:reports={reports},eps_{year}={eps_now},eps_{year+1}={eps_next}')
            if price is None:
                reason_parts.append('current_price_missing')
            companies.append({
                'code': code, 'name': name, 'cycle_tag': matched_tag, 'current_price': price,
                'valuation_status': 'unavailable', 'valuation_model': 'normalized_forward_cycle_low_risk',
                'execution_state': 'input_data_insufficient',
                'forward_earnings_basis': f'{year}/{year+1} consensus plus neutral commodity anchor, 6-18m regime and price-history calibration are mandatory for resource valuation.',
                'commodity_anchors': anchors, 'reasonable_multiple_range': None,
                'value_anchor_range': None, 'safe_buy_range': None, 'reasonable_buy_range': None,
                'left_conclusion': 'unavailable', 'reason': ';'.join(reason_parts),
                'cycle_regime': regime.get('regime') if regime else None,
                'invalidation_condition': gate.get('invalidation_condition') or 'cycle earnings bridge invalidated',
            })
            continue

        if eps_next is None:
            eps_next = eps_now
        forward_eps, current_weight, next_weight = calendar_forward_eps(eps_now, eps_next, now)
        earnings_trend = (eps_next / eps_now - 1.0) if eps_now else None
        sensitivity = float(policy.get('earnings_sensitivity', 0.8))
        short_term_effect = max(-max_short_effect, min(max_short_effect, weighted_short_delta * sensitivity))
        low_risk_short_effect = min(0.0, short_term_effect)
        normalized_forward_eps, neutralization_factor = normalize_forward_eps(
            forward_eps, weighted_neutral_delta, sensitivity, neutral_policy
        )

        if regime:
            regime_factors = regime.get('bear_base_bull_earnings_factor')
            multiple = regime.get('multiple_range_by_regime') or policy.get('fallback_multiple_range')
            regime_name = regime.get('regime')
        else:
            regime_factors = [0.92, 1.0, 1.08]
            multiple = policy.get('fallback_multiple_range')
            regime_name = 'machine_anchor_only_nonresource'
        if not isinstance(regime_factors, list) or len(regime_factors) != 3:
            raise RuntimeError(f'invalid cycle regime factors:{code}:{regime_factors}')
        if not isinstance(multiple, list) or len(multiple) != 2:
            raise RuntimeError(f'invalid cycle multiple range:{code}:{multiple}')

        scenario_eps = [max(0.01, normalized_forward_eps * float(f) * (1.0 + low_risk_short_effect)) for f in regime_factors]
        bear_eps, base_eps, bull_eps = scenario_eps
        mult_lo, mult_hi = float(multiple[0]), float(multiple[1])
        fair_floor = base_eps * mult_lo
        scenario_fair_range = [bear_eps * mult_lo, bull_eps * mult_hi]
        market_anchor = load_market_price_anchor(code, market_policy) if is_resource else None
        safe, reasonable, value_range, calibration_method = calibrate_low_risk_buy_bands(
            fair_floor, market_anchor, policy, market_policy
        )
        if price <= safe[1]:
            conclusion = 'safe_buy_zone'
        elif price <= reasonable[1]:
            conclusion = 'reasonable_buy_zone'
        else:
            conclusion = 'above_buy_zone'

        row = {
            'code': code, 'name': name, 'cycle_tag': matched_tag, 'current_price': round(price, 3),
            'valuation_status': 'valid', 'execution_state': 'valid', 'valuation_model': 'normalized_forward_cycle_low_risk',
            'valuation_basis_unit': 'PE',
            'forecast_source': 'akshare.stock_profit_forecast_em', 'forecast_report_count': reports,
            'consensus_eps_current_year': round(eps_now, 4), 'consensus_eps_next_year': round(eps_next, 4),
            'next_year_eps_growth_pct': round(earnings_trend * 100, 2) if earnings_trend is not None else None,
            'forward_12m_eps_proxy': round(forward_eps, 4),
            'forward_eps_weights': {'current_year': round(current_weight, 4), 'next_year': round(next_weight, 4)},
            'normalized_forward_eps': round(normalized_forward_eps, 4),
            'neutralization_factor': round(neutralization_factor, 4),
            'weighted_neutral_commodity_delta': round(weighted_neutral_delta, 4),
            'market_forward_pe_current_year': round(price / eps_now, 2),
            'market_forward_pe_next_year': round(price / eps_next, 2),
            'market_forward_pe_12m_proxy': round(price / forward_eps, 2),
            'market_pe_dynamic': round(spot.get(code, {}).get('pe_dynamic'), 4) if num(spot.get(code, {}).get('pe_dynamic')) else None,
            'commodity_anchors': anchors,
            'short_term_anchor_effect_on_eps': round(short_term_effect, 4),
            'low_risk_short_term_effect_on_eps': round(low_risk_short_effect, 4),
            'profit_sensitivity': sensitivity,
            'cycle_regime': regime_name,
            'cycle_regime_reviewed_at': regime_registry.get('reviewed_at'),
            'cycle_regime_age_days': regime_age_days,
            'cycle_regime_summary': regime.get('summary') if regime else 'No structured resource regime required for this non-resource cycle tag.',
            'cycle_regime_scores': {
                'supply': regime.get('supply_score') if regime else None,
                'demand': regime.get('demand_score') if regime else None,
                'inventory': regime.get('inventory_score') if regime else None,
            },
            'cycle_regime_evidence': regime.get('evidence', []) if regime else [],
            'bear_base_bull_regime_factor': [round(float(x), 4) for x in regime_factors],
            'bear_base_bull_forward_eps': [round(x, 4) for x in scenario_eps],
            'forward_earnings_basis': f'{year}/{year+1} consensus -> forward-12m EPS {forward_eps:.4f} -> neutral commodity normalization factor {neutralization_factor:.4f} -> structured 6-18m regime -> positive short-term commodity strength does not raise low-risk buy zones.',
            'reasonable_multiple_range': [mult_lo, mult_hi],
            'multiple_rationale': regime.get('summary') if regime else policy.get('rationale') or 'Versioned cycle multiple after normalized earnings.',
            'scenario_fair_value_range': [round(scenario_fair_range[0], 2), round(scenario_fair_range[1], 2)],
            'normalized_base_fair_value_floor': round(fair_floor, 2),
            'base_fair_value_floor': round(fair_floor, 2),
            'market_price_anchor_180d': market_anchor,
            'price_calibration_method': calibration_method,
            'value_anchor_range': [round(value_range[0], 2), round(value_range[1], 2)],
            'safe_buy_range': [round(safe[0], 2), round(safe[1], 2)],
            'reasonable_buy_range': [round(reasonable[0], 2), round(reasonable[1], 2)],
            'key_sensitivities': ['neutral commodity price', '6-18m supply-demand regime', 'next-year consensus EPS', '180d market price distribution', 'production/sales'],
            'invalidation_condition': gate.get('invalidation_condition') or 'cycle regime or company earnings transmission reverses',
            'left_conclusion': conclusion,
        }
        if conclusion in {'safe_buy_zone', 'reasonable_buy_zone'}:
            left.append(code)
        companies.append(row)

    payload = {
        'schema_version': 4,
        'generated_at': datetime.now(TZ).isoformat(),
        'reference_trade_date': reference_trade_date,
        'max_anchor_age_days': MAX_ANCHOR_AGE_DAYS,
        'cycle_regime_registry_reviewed_at': regime_registry.get('reviewed_at'),
        'cycle_regime_age_days': regime_age_days,
        'max_cycle_regime_age_days': max_regime_age,
        'common_pool_count': len(common.get('common_pool_codes', [])),
        'cycle_company_count': len(companies), 'cycle_codes': sorted(cycle_codes),
        'resource_cycle_codes': sorted([r['code'] for r in companies if r.get('cycle_tag') in RESOURCE_TAGS]),
        'anchor_errors': anchor_errors,
        'companies': companies, 'left_set_codes': sorted(left),
        'method_note': 'Resource low-risk valuation first normalizes current+next-year consensus against a long-window neutral commodity/cost anchor, then applies the reviewed 6-18m regime. Positive short-term commodity strength cannot lift a low-risk buy zone. Final value/safe/reasonable bands are calibrated against the stock own bounded 180-session price distribution and MA60 ceiling; theoretical bear/base/bull values are retained separately as scenario_fair_value_range.',
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'ok', 'cycle': len(companies), 'left': len(left), 'reference_trade_date': reference_trade_date, 'regime_age_days': regime_age_days, 'anchor_errors': anchor_errors}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())