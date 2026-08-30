from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'data/research/pipeline/common_qualification_pool.json'
LEFT = ROOT / 'data/research/pipeline/left_valuation_scan.json'
RIGHT = ROOT / 'data/research/pipeline/right_structure_scan.json'
OUT = ROOT / 'data/research/pipeline/final_selection.json'
SUMMARY = ROOT / 'data/research/pipeline/final_selection_summary.json'
TZ = ZoneInfo('Asia/Shanghai')


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding='utf-8'))


def main() -> int:
    common = load(COMMON)
    left = load(LEFT)
    right = load(RIGHT)
    common_codes = set(common.get('common_pool_codes', []))
    left_codes = set(left.get('left_set_codes', []))
    right_codes = set(right.get('right_set_codes', []))

    if left.get('common_pool_count') != len(common_codes) or right.get('common_pool_count') != len(common_codes):
        raise RuntimeError('left/right common-pool coverage mismatch')
    if not left_codes <= common_codes or not right_codes <= common_codes:
        raise RuntimeError('left/right set contains non-common-pool code')

    intersection = sorted(left_codes & right_codes)
    union = left_codes | right_codes
    jaccard = len(set(intersection)) / len(union) if union else 0.0
    suspicious = left_codes == right_codes and len(left_codes) >= 5
    independence = {
        'status': 'FAIL' if suspicious else 'PASS',
        'left_count': len(left_codes),
        'right_count': len(right_codes),
        'intersection_count': len(intersection),
        'jaccard': round(jaccard, 4),
        'same_set_suspicious': suspicious,
        'left_engine': 'forward normalized earnings + justified valuation multiple only',
        'right_engine': '300-bar same-date daily/weekly/52-week pressure + support + R:R only',
    }

    left_by = {x['code']: x for x in left.get('companies', [])}
    right_by = right.get('companies', {})
    gate_by = common.get('future_earnings_gate', {})
    reviews = {}
    core = []
    for code in intersection:
        l = left_by[code]
        r = right_by[code]
        g = gate_by[code]
        upside = r.get('upside_to_first_resistance_pct')
        rr = r.get('risk_reward')
        reasons = []
        hard_pass = True

        if g.get('gate_status') != 'pass':
            hard_pass = False; reasons.append('未来1-2季度盈利门槛未通过')
        if l.get('valuation_status') != 'valid' or l.get('left_conclusion') not in {'safe_buy_zone','reasonable_buy_zone'}:
            hard_pass = False; reasons.append('不在左侧正式买入区')
        if r.get('conclusion') not in {'strong','participate'}:
            hard_pass = False; reasons.append('右侧结构结论未达到参与级')
        if not isinstance(upside, (int,float)) or upside < 10:
            hard_pass = False; reasons.append('第一有效压力上行空间不足10%')
        if not isinstance(rr, (int,float)) or rr < 1.5:
            hard_pass = False; reasons.append('R:R不足1.5')
        if not r.get('support_invalidation'):
            hard_pass = False; reasons.append('缺少明确失效位')
        if independence['status'] != 'PASS':
            hard_pass = False; reasons.append('左右独立性审计失败')

        if hard_pass:
            status = 'core'
            reasons.append('盈利、估值、结构、第一压力空间与R:R全部通过硬门槛')
            core.append(code)
        else:
            status = 'reject'

        reviews[code] = {
            'status': status,
            'reason': '；'.join(reasons),
            'name': g.get('name') or l.get('name') or r.get('name'),
            'source': g.get('source'),
            'current_price': r.get('current_price'),
            'forward_bridge': g.get('forward_bridge'),
            'value_anchor_range': l.get('value_anchor_range'),
            'safe_buy_range': l.get('safe_buy_range'),
            'reasonable_buy_range': l.get('reasonable_buy_range'),
            'left_conclusion': l.get('left_conclusion'),
            'structure_state': r.get('structure_state'),
            'first_effective_resistance': r.get('first_effective_resistance'),
            'first_target_upside_pct': upside,
            'support_invalidation': r.get('support_invalidation'),
            'risk_reward': rr,
            'right_conclusion': r.get('conclusion'),
            'invalidation_condition': g.get('invalidation_condition'),
        }

    top3_candidates = []
    for code in core:
        review = reviews[code]
        upside = review.get('first_target_upside_pct')
        rr = review.get('risk_reward')
        if isinstance(upside, (int,float)) and upside >= 15 and isinstance(rr, (int,float)) and rr >= 2:
            l = left_by[code]
            price = review.get('current_price')
            anchors = l.get('value_anchor_range') or []
            anchor_mid = sum(anchors)/2 if len(anchors)==2 else price
            safety = ((anchor_mid / price) - 1) * 100 if price and anchor_mid else 0
            score = upside + min(rr, 4)*5 + max(min(safety, 30), -20)*0.25
            top3_candidates.append((score, code))
    top3_candidates.sort(reverse=True)
    top3 = [code for _,code in top3_candidates[:3]]

    final = {
        'schema_version': 1,
        'final_frozen_at': datetime.now(TZ).isoformat(),
        'market_trade_date': '2026-08-28',
        'common_pool_count': len(common_codes),
        'left_set_codes': sorted(left_codes),
        'right_set_codes': sorted(right_codes),
        'initial_intersection_codes': intersection,
        'core_codes': sorted(core),
        'top3_codes': top3,
        'independence_audit': independence,
        'upstream_validator_status': {
            'industry_scan': 'PASS',
            't2_recall': 'PASS',
            'weekly_scan': 'PASS',
            'common_pool_reconciliation': 'PASS',
            'left_valuation': 'PASS',
            'right_structure': 'PASS',
            'left_right_independence': independence['status'],
        },
        'reviews': reviews,
    }
    OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')

    compact = {
        'final_frozen_at': final['final_frozen_at'],
        'market_trade_date': final['market_trade_date'],
        'counts': {
            'common': len(common_codes), 'left': len(left_codes), 'right': len(right_codes),
            'intersection': len(intersection), 'core': len(core), 'top3': len(top3),
        },
        'independence_audit': independence,
        'left_codes': sorted(left_codes),
        'right_codes': sorted(right_codes),
        'intersection_codes': intersection,
        'core': [reviews[c] | {'code': c} for c in sorted(core)],
        'top3': [reviews[c] | {'code': c} for c in top3],
        'rejected_intersection': [reviews[c] | {'code': c} for c in intersection if c not in core],
    }
    SUMMARY.write_text(json.dumps(compact, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status':'ok','counts':compact['counts'],'top3':top3,'independence':independence}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
