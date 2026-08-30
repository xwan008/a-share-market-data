from __future__ import annotations

import json, math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'data/research/pipeline/common_qualification_pool.json'
LATEST=ROOT/'data/latest.json'
OUT=ROOT/'data/research/pipeline/left_valuation_scan.json'
TZ=ZoneInfo('Asia/Shanghai')

WEEKLY_RANGES={
 '000338':(12,16),'600066':(13,17),'600458':(16,22),'600482':(18,24),'600685':(18,24),'600710':(10,14),
 '603088':(18,24),'603259':(20,28),'603659':(18,25),'002475':(18,24),'603986':(25,32),'601869':(22,30),
 '001309':(22,30),'002709':(20,28),'002812':(18,25)
}
ONE_OFF_UNAVAILABLE={'002156':'H1归母利润受产业投资收益明显增厚，本轮未取得足够精确的扣非EPS/股本桥，不能用归母EPS年化形成正式价值锚。'}
CYCLE_KEYS=('铜矿资源','电解铝','动力煤','氟化工','氨纶')
FIN_KEYS=('证券','保险')

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def pe_range(tags,code):
    if code in WEEKLY_RANGES:return WEEKLY_RANGES[code], 'weekly_business_specific_PE'
    s=' '.join(tags)
    if any(k in s for k in CYCLE_KEYS): return None,'commodity_anchor_required'
    if any(k in s for k in FIN_KEYS): return None,'PB_ROE_bridge_required'
    if '船舶制造' in s:return (16,22),'shipbuilding_forward_PE'
    if '重卡' in s:return (12,16),'heavy_truck_forward_PE'
    if 'CXO' in s or 'CDMO' in s:return (20,28),'CXO_forward_PE'
    if '特高压' in s or '电网一次设备' in s:return (18,25),'grid_equipment_forward_PE'
    if 'AI服务器' in s:return (20,28),'AI_server_forward_PE'
    if '高速光模块' in s:return (22,30),'optical_forward_PE'
    if 'PCB/CCL' in s:return (20,28),'PCB_CCL_forward_PE'
    return None,'unsupported_business_model'

def main():
    import akshare as ak
    common=json.loads(COMMON.read_text(encoding='utf-8'))
    latest=json.loads(LATEST.read_text(encoding='utf-8'))
    stocks=latest.get('stocks',{})
    df=ak.stock_yjbb_em(date='20260630')
    eps={str(r['股票代码']).zfill(6):num(r.get('每股收益')) for _,r in df.iterrows()}
    companies=[]; left=[]
    for code in common.get('common_pool_codes',[]):
        gate=common['future_earnings_gate'][code]
        name=gate.get('name') or (stocks.get(code) or {}).get('name') or code
        price=num((stocks.get(code) or {}).get('price'))
        tags=gate.get('t2_tags') or []
        e=eps.get(code)
        rng,model=pe_range(tags,code)
        reason=None
        if code in ONE_OFF_UNAVAILABLE:
            rng=None; model='one_off_normalization_unavailable'; reason=ONE_OFF_UNAVAILABLE[code]
        if e is None or e<=0:
            rng=None; reason=reason or '2026H1 EPS缺失或非正，无法用本模型形成可审计的前瞻盈利中枢。'
        if price is None:
            rng=None; reason=reason or '当前价格缺失。'
        if rng is None:
            row={'code':code,'name':name,'current_price':price,'valuation_status':'unavailable','valuation_model':model,
                 'forward_earnings_basis':'未来1-2季度盈利门槛已通过，但本业务缺少完整商品锚/PB-ROE/一次性收益归一化桥，拒绝用TTM估值替代。',
                 'reasonable_multiple_range':None,'value_anchor_range':None,'reasonable_buy_range':None,'safe_buy_range':None,
                 'key_sensitivities':['盈利桥持续性','估值模型所需的专用锚'],
                 'invalidation_condition':gate.get('invalidation_condition') or '未来盈利桥失效','left_conclusion':'unavailable','reason':reason or model}
        else:
            factor=1.0 if gate.get('source') in ('weekly','both') else 0.90
            if code=='603986': factor*=0.71
            fwd=e*2*factor
            lo=fwd*rng[0]; hi=fwd*rng[1]; mid=(lo+hi)/2
            safe=[lo*0.70,lo*0.85]
            reasonable=[lo*0.85,mid*0.95]
            if price<=safe[1]: concl='safe_buy_zone'
            elif price<=reasonable[1]: concl='reasonable_buy_zone'
            else: concl='above_buy_zone'
            row={'code':code,'name':name,'current_price':round(price,3),'valuation_status':'valid','valuation_model':model,
                 'h1_eps':round(e,4),'normalization_factor':factor,'forward_normalized_eps':round(fwd,4),
                 'forward_earnings_basis':f'2026H1 EPS×2×{factor:.2f}; 仅在已通过未来1-2季度盈利门槛后作为保守盈利中枢代理。',
                 'reasonable_multiple_range':list(rng),'value_anchor_range':[round(lo,2),round(hi,2)],
                 'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)],'safe_buy_range':[round(safe[0],2),round(safe[1],2)],
                 'key_sensitivities':['未来1-2季度盈利兑现','合理估值区间','H2季节性/利润率'],
                 'invalidation_condition':gate.get('invalidation_condition') or '未来盈利桥失效','left_conclusion':concl}
            if concl in ('safe_buy_zone','reasonable_buy_zone'): left.append(code)
        companies.append(row)
    payload={'schema_version':1,'generated_at':datetime.now(TZ).isoformat(),'common_pool_count':len(common.get('common_pool_codes',[])),
             'companies':companies,'left_set_codes':sorted(left),'method_note':'TTM PE is not used as valuation engine; unavailable is preferred to an incomplete mandatory bridge.'}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','common':payload['common_pool_count'],'left':len(left),'valid':sum(x['valuation_status']=='valid' for x in companies)},ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
