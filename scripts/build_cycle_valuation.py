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
POLICY = ROOT / 'config/cycle_valuation_policy.json'
OUT = ROOT / 'data/research/pipeline/cycle_valuation.json'
TZ = ZoneInfo('Asia/Shanghai')
CYCLE_TAGS = ('nonferrous::铜矿资源', 'nonferrous::电解铝', 'coal::动力煤', 'chemicals::氟化工', 'chemicals::氨纶')
RESOURCE_TAGS = ('nonferrous::铜矿资源', 'nonferrous::电解铝')


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


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


def fetch_anchor(ak, symbol: str) -> dict:
    df = ak.futures_zh_daily_sina(symbol=symbol)
    if df is None or df.empty:
        raise RuntimeError(f'empty futures series:{symbol}')
    close_col = next((c for c in df.columns if str(c).lower() == 'close'), None)
    date_col = next((c for c in df.columns if str(c).lower() == 'date'), None)
    if close_col is None:
        raise RuntimeError(f'close column missing:{symbol}:{list(df.columns)}')
    vals = [num(x) for x in df[close_col].tolist()]
    vals = [x for x in vals if x is not None and x > 0]
    if len(vals) < 60:
        raise RuntimeError(f'insufficient futures history:{symbol}:{len(vals)}')
    current = vals[-1]
    ma20 = sum(vals[-20:]) / 20
    ma60 = sum(vals[-60:]) / 60
    high60 = max(vals[-60:])
    return {
        'symbol': symbol,
        'last_date': str(df.iloc[-1][date_col]) if date_col is not None else None,
        'current': current,
        'ma20': ma20,
        'ma60': ma60,
        'current_to_ma20': current / ma20,
        'current_to_ma60': current / ma60,
        'drawdown_from_60d_high_pct': (current / high60 - 1) * 100,
        'trend_20_vs_60_pct': (ma20 / ma60 - 1) * 100,
    }


def policy_for(tags: list[str], code: str, cfg: dict) -> tuple[str | None, dict | None]:
    matched = next((t for t in tags if t in CYCLE_TAGS), None)
    if not matched:
        return None, None
    base = dict(cfg.get('subchain_policies', {}).get(matched, {}))
    override = cfg.get('company_overrides', {}).get(code, {})
    if override:
        base.update(override)
    return matched, base or None


def main() -> int:
    import akshare as ak

    common = load(COMMON)
    latest = load(LATEST)
    cfg = load(POLICY)
    stocks = latest.get('stocks', {})
    consensus = load_consensus(ak)
    year = datetime.now(TZ).year
    scenario_cfg = cfg.get('scenario_rules', {})
    clip_lo, clip_hi = scenario_cfg.get('base_anchor_ratio_clip', [0.85, 1.15])
    bear_shock = float(scenario_cfg.get('bear_shock', -0.08))
    bull_shock = float(scenario_cfg.get('bull_shock', 0.08))

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

        if not policy or not policy.get('anchors'):
            companies.append({
                'code': code, 'name': name, 'cycle_tag': matched_tag, 'current_price': price,
                'valuation_status': 'unavailable', 'valuation_model': 'manual_spread_anchor_required',
                'forward_earnings_basis': '该细分链尚无可机械验证的商品/价差锚；不得退回TTM PE。',
                'commodity_anchors': [], 'reasonable_multiple_range': None, 'value_anchor_range': None,
                'safe_buy_range': None, 'reasonable_buy_range': None, 'left_conclusion': 'unavailable',
                'reason': 'cycle_policy_missing_machine_readable_anchor',
                'invalidation_condition': gate.get('invalidation_condition') or '周期盈利桥失效',
            })
            continue

        anchors = []
        weighted_delta = 0.0
        missing = []
        for a in policy.get('anchors', []):
            symbol = a['symbol']
            if symbol not in anchor_cache and symbol not in anchor_errors:
                try:
                    anchor_cache[symbol] = fetch_anchor(ak, symbol)
                except Exception as exc:
                    anchor_errors[symbol] = f'{type(exc).__name__}:{exc}'
            if symbol in anchor_errors:
                missing.append(symbol)
                continue
            m = anchor_cache[symbol]
            weight = float(a.get('weight', 1.0))
            direction = float(a.get('direction', 1.0))
            delta = (m['current_to_ma60'] - 1.0) * direction
            weighted_delta += weight * delta
            anchors.append({**m, 'weight': weight, 'direction': direction})

        c = consensus.get(code, {'report_count': 0, 'eps': {}})
        eps = num(c.get('eps', {}).get(year))
        reports = int(c.get('report_count') or 0)
        if missing or eps is None or reports < 3 or price is None:
            reason_parts = []
            if missing:
                reason_parts.append(f'commodity_anchor_fetch_failed:{missing}')
            if eps is None or reports < 3:
                reason_parts.append(f'forward_consensus_insufficient:reports={reports},eps={eps}')
            if price is None:
                reason_parts.append('current_price_missing')
            companies.append({
                'code': code, 'name': name, 'cycle_tag': matched_tag, 'current_price': price,
                'valuation_status': 'unavailable', 'valuation_model': 'commodity_scenario_forward_pe',
                'forward_earnings_basis': f'{year}一致预期EPS经商品锚压力测试；缺少关键输入时禁止形成正式价值锚。',
                'commodity_anchors': anchors, 'reasonable_multiple_range': policy.get('multiple_range'),
                'value_anchor_range': None, 'safe_buy_range': None, 'reasonable_buy_range': None,
                'left_conclusion': 'unavailable', 'reason': ';'.join(reason_parts),
                'invalidation_condition': gate.get('invalidation_condition') or '周期盈利桥失效',
            })
            continue

        base_anchor_factor = min(max(1.0 + weighted_delta, float(clip_lo)), float(clip_hi))
        bear_anchor_factor = max(0.70, base_anchor_factor + bear_shock)
        bull_anchor_factor = min(1.30, base_anchor_factor + bull_shock)
        sensitivity = float(policy.get('earnings_sensitivity', 0.8))

        def stress(anchor_factor: float) -> float:
            return max(0.01, eps * (1.0 + sensitivity * (anchor_factor - 1.0)))

        bear_eps = stress(bear_anchor_factor)
        base_eps = stress(base_anchor_factor)
        bull_eps = stress(bull_anchor_factor)
        pe_lo, pe_hi = [float(x) for x in policy.get('multiple_range')]
        fair_floor = base_eps * pe_lo
        value_range = [bear_eps * pe_lo, bull_eps * pe_hi]
        safe_band = policy.get('safe_to_fair_floor', [0.75, 0.88])
        reasonable_band = policy.get('reasonable_to_fair_floor', [0.88, 1.0])
        safe = [fair_floor * safe_band[0], fair_floor * safe_band[1]]
        reasonable = [fair_floor * reasonable_band[0], fair_floor * reasonable_band[1]]
        if price <= safe[1]:
            conclusion = 'safe_buy_zone'
        elif price <= reasonable[1]:
            conclusion = 'reasonable_buy_zone'
        else:
            conclusion = 'above_buy_zone'

        row = {
            'code': code, 'name': name, 'cycle_tag': matched_tag, 'current_price': round(price, 3),
            'valuation_status': 'valid', 'valuation_model': 'commodity_scenario_forward_pe',
            'forecast_source': 'akshare.stock_profit_forecast_em', 'forecast_report_count': reports,
            'consensus_eps_current_year': round(eps, 4),
            'commodity_anchors': anchors,
            'profit_sensitivity': sensitivity,
            'bear_base_bull_anchor_factor': [round(bear_anchor_factor, 4), round(base_anchor_factor, 4), round(bull_anchor_factor, 4)],
            'bear_base_bull_forward_eps': [round(bear_eps, 4), round(base_eps, 4), round(bull_eps, 4)],
            'forward_earnings_basis': f'{year}一致预期EPS={eps:.4f} → 商品/成本锚相对60日中枢 → sensitivity={sensitivity:.2f} → bear/base/bull盈利。',
            'reasonable_multiple_range': [pe_lo, pe_hi],
            'multiple_rationale': policy.get('rationale') or '按资源/周期业务质量和周期波动采用版本化估值区间。',
            'value_anchor_range': [round(value_range[0], 2), round(value_range[1], 2)],
            'base_fair_value_floor': round(fair_floor, 2),
            'safe_buy_range': [round(safe[0], 2), round(safe[1], 2)],
            'reasonable_buy_range': [round(reasonable[0], 2), round(reasonable[1], 2)],
            'key_sensitivities': ['商品价格中枢', '成本锚', '产量/销量', '一致预期EPS修正'],
            'invalidation_condition': gate.get('invalidation_condition') or '商品锚与公司盈利传导同时逆转',
            'left_conclusion': conclusion,
        }
        if conclusion in {'safe_buy_zone', 'reasonable_buy_zone'}:
            left.append(code)
        companies.append(row)

    payload = {
        'schema_version': 1,
        'generated_at': datetime.now(TZ).isoformat(),
        'common_pool_count': len(common.get('common_pool_codes', [])),
        'cycle_company_count': len(companies),
        'cycle_codes': sorted(cycle_codes),
        'resource_cycle_codes': sorted([r['code'] for r in companies if r.get('cycle_tag') in RESOURCE_TAGS]),
        'anchor_errors': anchor_errors,
        'companies': companies,
        'left_set_codes': sorted(left),
        'method_note': 'Resource cycle valuation cannot terminate at commodity_anchor_required when machine-readable anchors are available; commodity trend is an explicit upstream earnings input.',
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'ok', 'cycle': len(companies), 'left': len(left), 'anchor_errors': anchor_errors}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
