from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('forward_base', ROOT / 'scripts/build_forward_valuation.py')
BASE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(BASE)
CONSENSUS_CACHE = None


def latest_financial_bvps(ak, code: str) -> tuple[float | None, str | None, str | None]:
    """Use reported per-share net assets from Sina financial indicators; no real-time PB dependency."""
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year=str(datetime.now().year - 2))
    except Exception as exc:
        return None, None, f'{type(exc).__name__}:{exc}'
    if df is None or df.empty:
        return None, None, 'empty_financial_indicator'
    date_col = next((c for c in df.columns if str(c) == '日期'), None)
    bps_cols = [
        next((c for c in df.columns if '每股净资产_调整后' in str(c)), None),
        next((c for c in df.columns if '每股净资产_调整前' in str(c)), None),
        next((c for c in df.columns if '调整后的每股净资产' in str(c)), None),
    ]
    bps_cols = [c for c in bps_cols if c is not None]
    if not date_col or not bps_cols:
        return None, None, f'bvps_columns_missing:{list(df.columns)}'
    tmp = df.copy(); tmp['_date'] = tmp[date_col].astype(str); tmp = tmp.sort_values('_date', ascending=False)
    for _, row in tmp.iterrows():
        for col in bps_cols:
            value = BASE.num(row.get(col))
            if value is not None and value > 0:
                return value, str(row.get(date_col))[:10], None
    return None, None, 'no_positive_bvps'


def load_financial_indicators(ak):
    common = BASE.load(BASE.COMMON); latest = BASE.load(BASE.LATEST); policies = BASE.load(BASE.POLICY)
    stocks = latest.get('stocks', {}); out = {}; errors = []
    year = datetime.now(BASE.TZ).year; min_reports = int(policies.get('forecast_policy', {}).get('minimum_report_count', 3))
    consensus = CONSENSUS_CACHE or {}
    for code in common.get('common_pool_codes', []):
        gate = common['future_earnings_gate'][code]; text = ' '.join(gate.get('t2_tags') or [])
        if '证券' not in text and '保险' not in text: continue
        c = consensus.get(code, {'report_count': 0, 'eps': {}})
        if int(c.get('report_count') or 0) < min_reports or BASE.num(c.get('eps', {}).get(year)) is None: continue
        price = BASE.num((stocks.get(code) or {}).get('price'))
        if price is None or price <= 0: continue
        bvps, report_date, err = latest_financial_bvps(ak, code)
        if err:
            errors.append(f'{code}:{err}'); continue
        out[code] = {'pb': price / bvps, 'pe_dynamic': None, 'source': 'akshare.stock_financial_analysis_indicator(Sina)_reported_BVPS', 'reported_bvps': bvps, 'reported_bvps_date': report_date}
    return out, errors


def main() -> int:
    import akshare as ak
    global CONSENSUS_CACHE
    CONSENSUS_CACHE = BASE.load_consensus(ak)
    BASE.load_consensus = lambda _: CONSENSUS_CACHE
    BASE.load_spot_indicators = load_financial_indicators
    return BASE.main()


if __name__ == '__main__':
    raise SystemExit(main())
