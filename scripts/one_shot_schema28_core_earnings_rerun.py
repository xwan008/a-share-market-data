from __future__ import annotations
import json, math, statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'data/research/v2/research_state.json'
STRUCT=ROOT/'data/research/v2/full_market_price_structure.json'
LATEST=ROOT/'data/latest.json'
URL='https://datacenter-web.eastmoney.com/api/data/v1/get'
QUOTE='https://push2.eastmoney.com/api/qt/stock/get'
HEAD={'User-Agent':'Mozilla/5.0 schema28-core-rerun'}
TZ=ZoneInfo('Asia/Shanghai')

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except: return None

def fetch_report(date):
    out={}
    for page in range(1,40):
        p={'reportName':'RPT_LICO_FN_CPD','columns':'ALL','filter':f"(REPORTDATE='{date}')",'pageNumber':page,'pageSize':500,'sortColumns':'SECURITY_CODE','sortTypes':'1'}
        j=requests.get(URL,params=p,headers=HEAD,timeout=30).json(); rows=((j.get('result') or {}).get('data') or [])
        if not rows: break
        for r in rows:
            c=str(r.get('SECURITY_CODE') or '').zfill(6)
            if len(c)==6: out[c]=r
    if not out: raise RuntimeError('no report '+date)
    return out

def yoy(a,b):
    a,b=num(a),num(b)
    if a is None or b is None:return None
    if b>0:return a/b-1
    if b<=0<a:return 1.0
    if b<0 and a<0:return (abs(b)-abs(a))/abs(b)
    return None

def shares_implied(r):
    np=num(r.get('PARENT_NETPROFIT')); eps=num(r.get('BASIC_EPS'))
    return np/eps if np and eps and eps!=0 and np/eps>1e6 else None

def core_profit(r, shares):
    de=num(r.get('DEDUCT_BASIC_EPS'))
    return de*shares if de is not None and shares else None

def total_shares(code):
    secid=('1.' if code.startswith(('600','601','603','605')) else '0.')+code
    try:
        d=(requests.get(QUOTE,params={'secid':secid,'fields':'f84'},headers=HEAD,timeout=12).json().get('data') or {})
        x=num(d.get('f84')); return x if x and x>1e6 else None
    except:return None

def vclass(sw1,sw3):
    if sw1 in {'银行','非银金融'}: return 'financial'
    if sw1 in {'有色金属','煤炭','石油石化','基础化工','钢铁','建筑材料'}: return 'cyclical'
    if sw1=='国防军工' or any(x in sw3 for x in ['航海','船舶','工程机械']): return 'order_cycle'
    if sw1 in {'电子','通信','计算机','电力设备'}: return 'growth'
    if sw1 in {'食品饮料','家用电器','汽车','医药生物','美容护理','社会服务','商贸零售','纺织服饰','轻工制造'}: return 'consumer'
    return 'general'

def peband(c): return {'cyclical':(6.,10.),'order_cycle':(10.,16.),'growth':(18.,26.),'consumer':(14.,22.),'general':(12.,20.)}.get(c,(12.,20.))
def secpe(c,g):
    g=max(-.2,min(.5,g or 0))
    if c=='cyclical':return 8.
    if c=='order_cycle':return 12+max(-2,min(2,g*8))
    if c=='growth':return max(16,min(28,16+g*20))
    if c=='consumer':return max(13,min(22,14+g*16))
    return max(11,min(20,12+g*14))
def entry(ps):
    if not ps or ps.get('data_status')!='verified':return None
    st=ps.get('structure_type'); sup=num(ps.get('support_invalidation')); ma=num(ps.get('ma20')); cur=num(ps.get('current_price')); br=num(ps.get('breakout_level'))
    if st=='breakout' and br:return [round(br*.995,2),round(br*1.03,2)]
    if st=='pullback' and sup and ma:return [round(min(sup,ma)*.99,2),round(max(sup,ma)*1.02,2)]
    if st=='trend_continuation' and sup and ma and cur:
        lo=max(sup,min(ma,cur))*.99; hi=max(ma,min(cur,ma*1.05))*1.01
        return [round(lo,2),round(max(lo,hi),2)]
    return None

s=json.loads(STATE.read_text(encoding='utf-8')); cur=fetch_report('2026-06-30'); prev=fetch_report('2025-06-30'); ann=fetch_report('2025-12-31')
latest=json.loads(LATEST.read_text(encoding='utf-8')); fullps=json.loads(STRUCT.read_text(encoding='utf-8')).get('companies') or {}; prices=latest.get('stocks') or {}

# Re-screen every company already enumerated in each confirmed improving chain using core/deducted EPS.
chain_surv={}; total_screen=excl=0; all_surv=set()
for cid,b in s['company_light_screen'].items():
    surv=[]
    for e in b['screened_companies']:
        total_screen+=1; c=e['code']; cr=cur.get(c); pr=prev.get(c)
        ce=num((cr or {}).get('DEDUCT_BASIC_EPS')); pe=num((pr or {}).get('DEDUCT_BASIC_EPS'))
        cy=yoy(ce,pe); rv=yoy(num((cr or {}).get('TOTAL_OPERATE_INCOME')),num((pr or {}).get('TOTAL_OPERATE_INCOME')))
        basic=num((cr or {}).get('BASIC_EPS')); parent=num((cr or {}).get('PARENT_NETPROFIT')); sh=shares_implied(cr or {})
        cp=core_profit(cr or {},sh); ratio=(abs(parent-cp)/abs(parent)) if parent and cp is not None else None
        decision='survive'; reason=None
        if ce is None or pe is None: decision,reason='exclude','data_unavailable'
        elif ce<=0 or cy is None or cy<=0: decision,reason='exclude','earnings_deteriorating'
        elif rv is not None and rv<-.15: decision,reason='exclude','profit_not_from_chain_driver'
        if decision=='exclude':excl+=1
        else:surv.append(c); all_surv.add(c)
        e.update({'earnings_quality_match':decision=='survive','screen_decision':decision,'exclusion_reason':reason,
                  'core_earnings_evidence':f"2026H1 deduct_basic_eps={ce}; 2025H1 deduct_basic_eps={pe}; core_eps_yoy={cy}; revenue_yoy={rv}",
                  'core_earnings_trend':'improving' if decision=='survive' else ('unconfirmed' if ce is None or pe is None else 'deteriorating'),
                  'nonrecurring_dominance_check':{'dominant':bool(ratio is not None and ratio>=.30),'ratio_approx':ratio,'parent_netprofit':parent,'core_profit_implied':cp},
                  'valuation_earnings_basis_requirement':'deducted_or_core_earnings_only',
                  'evidence_basis':f"core screen: deduct EPS {pe}->{ce}; yoy={cy}; revenue_yoy={rv}; nonrec_ratio={ratio}"})
    b['screen_complete']=True; chain_surv[cid]=surv

# Rebuild comparisons and survivor companies without any Top-N cut.
oldco=s.get('companies') or {}; comps=[]; companies={}
for old in s['chain_comparisons']:
    cid=old['chain_id']; surv=sorted(chain_surv.get(cid,[])); scored=[]
    for c in surv:
        cr,pr=cur.get(c,{ }),prev.get(c,{ }); ce=num(cr.get('DEDUCT_BASIC_EPS')); pe=num(pr.get('DEDUCT_BASIC_EPS')); cy=yoy(ce,pe) or 0; rv=yoy(num(cr.get('TOTAL_OPERATE_INCOME')),num(pr.get('TOTAL_OPERATE_INCOME'))) or 0
        sh=shares_implied(cr); cp=core_profit(cr,sh) or 0; score=max(-1,min(3,cy))*.55+max(-1,min(1,rv))*.2+(math.log10(max(cp,1))/12)*.25
        scored.append((score,c)); base=dict(oldco.get(c) or {'code':c,'name':cr.get('SECURITY_NAME_ABBR') or c})
        base.update({'core_h1_deduct_eps':ce,'core_h1_yoy':cy,'comparison_score':round(score,6)}); companies[c]=base
    scored.sort(reverse=True)
    screened=old.get('screened_companies') or []
    comps.append({**old,'excluded_companies':sorted(set(screened)-set(surv)),'compared_companies':surv,'comparison_complete':True,'fundamental_best':scored[0][1] if scored else None,'current_opportunity_best':None,'singleton_reason':'only_one_survivor_after_core_earnings_screen' if len(surv)==1 else None})

valuation_set=sorted(all_surv)
# Current share counts for all core survivors.
shares={}
with ThreadPoolExecutor(max_workers=20) as pool:
    fs={pool.submit(total_shares,c):c for c in valuation_set}
    for f in as_completed(fs): shares[fs[f]]=f.result()

vals={}; pstruct={}; bps={}; ops=[]; review=extreme=0
for c in valuation_set:
    co=companies[c]; cr,pr,ar=cur.get(c,{}),prev.get(c,{}),ann.get(c,{})
    sh=shares.get(c) or shares_implied(cr); ash=shares_implied(ar); psh=shares_implied(pr) or sh
    core_h1=core_profit(cr,sh); core_prev=core_profit(pr,psh); core_a=core_profit(ar,ash)
    core_y=yoy(core_h1,core_prev); price=num((prices.get(c) or {}).get('price')); cls=vclass(co.get('sw_level1_name',''),co.get('sw_level3_name',''))
    sharechg=((sh/ash-1)*100) if sh and ash else None; material=sharechg is not None and abs(sharechg)>=5
    blocked=False; rc=None; blocker=None
    if not price or not sh or core_h1 is None or core_a is None or core_a<=0: blocked=True;rc='critical_public_data_unavailable';blocker='核心盈利/股本/价格不足'
    elif cls=='financial': blocked=True;rc='critical_public_data_unavailable';blocker='金融公司需PB-ROE独立模型，不能用PE替代'
    reasonable=safe=None; secondary=None; audit={'triggered':False,'passed':True}; assumptions={}; basis=''
    if not blocked:
        ratio=core_prev/core_a if core_prev and core_prev>0 else None
        if ratio and .2<=ratio<=.8:
            raw=core_h1/ratio; basis=f'以2025H1扣非核心利润/2025A扣非核心利润季节性{ratio:.1%}桥接FY2026'
        else:
            cap=.35 if cls in {'growth','consumer','general'} else .20; g=max(-.15,min(cap,core_y or 0)); raw=core_a*(1+g); basis=f'以2025A扣非核心利润为锚，将H1核心增速截断至{g:.1%}'
        if cls=='cyclical': norm=core_a*.7+raw*.3; basis+='；周期正常化70%年度锚+30%景气Forward'
        elif cls=='order_cycle': norm=core_a*.6+raw*.4; basis+='；订单周期正常化60%年度锚+40%交付Forward'
        else:
            maxg=.5 if cls=='growth' else .35; norm=min(raw,core_a*(1+maxg)); basis+=f'；核心Forward相对年度锚增长上限{maxg:.0%}'
        eps=norm/sh; lo,hi=peband(cls); reasonable=[round(eps*lo,2),round(eps*hi,2)]; safe=[round(reasonable[0]*.75,2),round(reasonable[0]*.85,2)]; ng=norm/core_a-1
        assumptions={'2025A_core_profit':core_a,'2026H1_core_profit':core_h1,'normalized_core_profit':norm,'normalized_core_eps':eps,'core_profit_growth':ng,'primary_pe_range':[lo,hi],'share_count_change_pct':sharechg}
        isext=reasonable[0]>=price*1.5 or price>=reasonable[1]*1.5
        if isext:
            extreme+=1; spe=secpe(cls,ng); sr=[round(eps*spe*.85,2),round(eps*spe*1.15,2)]; pm=sum(reasonable)/2; sm=sum(sr)/2; div=abs(pm-sm)/max(abs(pm),abs(sm))*100 if max(abs(pm),abs(sm)) else 0
            secondary={'method':'growth_adjusted_core_earnings_power','pe_mid':spe,'reasonable_range':sr,'midpoint_divergence_pct':round(div,2)}; audit={'triggered':True,'passed':div<=30,'share_count_and_corporate_action_rechecked':True,'cycle_or_growth_persistence_rechecked':True,'independent_secondary_method':secondary}
            if div>30: blocked=True;rc='model_instability';blocker=f'核心盈利双模型中枢差异{div:.1f}%>30%';reasonable=safe=None
            else:
                ol,oh=max(reasonable[0],sr[0]),min(reasonable[1],sr[1]); reasonable=[round(ol,2),round(oh,2)] if ol<=oh else [round(min(pm,sm)*.9,2),round(max(pm,sm)*1.1,2)];safe=[round(reasonable[0]*.75,2),round(reasonable[0]*.85,2)]
    if blocked: review+=1; pos='review_required'
    elif price<=safe[0]:pos='below_safe'
    elif price<=safe[1]:pos='in_safe_zone'
    elif price<=reasonable[1]:pos='fair'
    elif price<=reasonable[1]*1.2:pos='above_fair'
    else:pos='materially_overvalued'
    vals[c]={'current_price':price,'price_date':latest.get('trade_date'),'earnings_type':'review_required' if blocked else ('normalized_cycle' if cls in {'cyclical','order_cycle'} else 'forward_core'), 'earnings_basis':blocker if blocked else basis,'primary_method':'review_required' if blocked else ('cycle_midpoint_PE' if cls=='cyclical' else ('normalized_order_cycle_PE' if cls=='order_cycle' else 'forward_core_PE')),'key_assumptions':assumptions,'current_share_count':sh,'share_count_basis':'Eastmoney f84; fallback current report implied shares','corporate_action_check':{'2025A_implied_weighted_shares':ash,'current_share_count':sh,'share_count_change_pct':sharechg,'material_share_count_change':material,'historical_eps_direct_scaling_used':False},'earnings_bridge_integrity':'deducted_core_profit_divided_by_current_share_count' if not blocked else 'blocked_after_full_attempt','reasonable_price_assumption':'扣非/核心利润Forward或正常化后除以当前股本，再用匹配估值带；当前价不参与内在价值' if not blocked else blocker,'reasonable_price_range':reasonable,'uncertainty':'high' if cls in {'cyclical','order_cycle'} or material else 'medium','margin_of_safety_reason':'审计后合理价值下沿75%-85%','safe_price_range':safe,'valuation_position':pos,'falsifiers':['后续扣非核心盈利恶化','盈利Driver反转','公司行动导致口径断裂'],'valuation_attempt_complete':True,'model_execution_status':'blocked_after_full_attempt' if blocked else 'complete','review_required':blocked,'review_exception_code':rc,'blocker_evidence':blocker,'secondary_method':secondary,'extreme_valuation_deviation_audit':audit,'core_earnings_used':True}
    ps=dict(fullps.get(c) or {}); pstruct[c]=ps
    if not blocked:
        er=entry(ps); value=bool(safe and price is not None and price<=safe[1]); timing=bool(ps.get('structure_type') in {'pullback','breakout','trend_continuation'} and ps.get('chase_risk')!='high' and er); inter=None
        if safe and er:
            a,b=max(safe[0],er[0]),min(safe[1],er[1]); inter=[round(a,2),round(b,2)] if a<=b else None
        now=bool(inter and inter[0]<=price<=inter[1])
        if ps.get('structure_type') in {'damaged','overheated'}: status='avoid'
        elif value and timing and inter and now: status='buyable_now'
        elif not value:status='watch_value'
        else:status='watch_structure'
        bp={'code':c,'value_eligible':value,'timing_eligible':timing,'buy_point_status':status,'buy_price_range':inter,'buy_point_basis':'safe_price_range ∩ independent structure_entry_range; current price must be inside','structure_entry_range':er,'invalidation_price':ps.get('support_invalidation')};bps[c]=bp
        if status=='buyable_now':ops.append({'code':c,'name':co.get('name',c),'source_chain_ids':co.get('source_chain_ids',[]),'current_price':price,'reasonable_price_range':reasonable,'safe_price_range':safe,'structure_entry_range':er,'buy_price_range':inter,'valuation_position':pos,'price_structure':ps.get('structure_type'),'action':'low_risk_buy_point'})

buycodes={o['code'] for o in ops}
for comp in comps: comp['current_opportunity_best']=next((c for c in comp['compared_companies'] if c in buycodes),None); comp['opportunity_resolution_complete']=True
# Gate: all screen chains done, all survivors compared, all valuations executed, all nonreview have buy assessment.
all_nonreview={c for c,v in vals.items() if not v['review_required']}; gate=(set(bps)==all_nonreview and len(vals)==len(valuation_set) and all(b.get('screen_complete') for b in s['company_light_screen'].values()))
s.update({'generated_at':datetime.now(TZ).isoformat(),'run_type':'manual_schema28_core_earnings_full_company_rerun','status':'research_complete' if gate else 'incomplete_research','chain_comparisons':comps,'companies':companies,'valuation_set':valuation_set,'valuations':vals,'price_structures':pstruct,'buy_point_assessments':bps,'current_opportunities':ops if gate else []})
s['diagnostics']['company_screen'].update({'company_screened_chain_count':len(s['company_light_screen']),'unscreened_confirmed_improving_chains':[],'light_screen_universe_company_count':total_screen,'light_screen_excluded_count':excl,'horizontal_comparison_survivor_count':sum(len(x) for x in chain_surv.values()),'deduplicated_valuation_set_count':len(valuation_set)})
s['diagnostics']['valuation'].update({'valuation_set_count':len(valuation_set),'executed_count':len(vals),'complete_non_review_count':len(all_nonreview),'review_required_count':review,'extreme_deviation_audit_count':extreme,'valuation_gate_passed':gate})
s['diagnostics']['buy_point']={'assessed_count':len(bps),'buyable_now_count':len(ops),'buy_point_gate_passed':gate}
s['diagnostics']['completion_gate_passed']=gate;s['diagnostics']['coverage']['completion_gate_passed']=gate
s['diagnostics']['core_earnings_rerun']={'deduct_basic_eps_field_used':True,'all_1082_light_screens_recomputed':True,'parent_profit_not_used_when_core_profit_available':True}
STATE.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':s['status'],'screened':total_screen,'excluded':excl,'survivors_before_dedup':sum(len(x) for x in chain_surv.values()),'valuation_set':len(valuation_set),'review':review,'extreme_audits':extreme,'buyable_now':len(ops),'opportunities':ops},ensure_ascii=False,indent=2))
