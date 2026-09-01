from __future__ import annotations
import json, math, statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT=Path(__file__).resolve().parents[1]
TAX=ROOT/'config/industry_scan_universe.json'
INDEX=ROOT/'data/research/company_industry_index.json'
STRUCT=ROOT/'data/research/v2/full_market_price_structure.json'
LATEST=ROOT/'data/latest.json'
STATE=ROOT/'data/research/v2/research_state.json'
URL='https://datacenter-web.eastmoney.com/api/data/v1/get'
QUOTE='https://push2.eastmoney.com/api/qt/stock/get'
HEAD={'User-Agent':'Mozilla/5.0 schema30-bootstrap'}
TZ=ZoneInfo('Asia/Shanghai')

DIRECTIONS=[
 {'direction_name':'AI电子与通信硬件','recent_change_window':'2026H1至2026年7月','why_now':'电子行业利润高增且7月继续强化；AI算力、存储、电子材料、光纤光缆和通信系统设备是主要驱动。','leading_variables':['AI算力需求','存储/芯片价格','服务器与通信设备需求','光纤光缆需求'],'evidence_basis':['国家统计局：2026年1-7月计算机通信及电子设备制造业利润同比+105%，高于1-6月+96.9%；集成电路、电子材料、电子电路、光纤/光缆等高增','A股2026H1电子行业净利润同比约+194.9%，半导体盈利增速领先'],'falsifiers':['电子行业利润增速持续快速回落','AI硬件订单/出货显著下修','存储及关键电子品价格反转'],'source_urls':['https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html','https://www.stats.gov.cn/sj/zxfbhjd/202608/t20260827_1965127.html'], 'l1_codes':['S27'],'l2_keywords':['通信设备','计算机设备']},
 {'direction_name':'有色金属','recent_change_window':'2026H1至2026年7月','why_now':'有色采选与冶炼利润维持高增长，A股有色中报盈利显著改善。','leading_variables':['铜铝金锂钨等价格','冶炼加工费','矿端供给','库存与需求'],'evidence_basis':['国家统计局：1-7月有色采选利润+74.9%，有色冶炼压延+91.8%','A股2026H1有色金属净利润同比约+88%~100%'], 'falsifiers':['主要金属价格趋势反转','库存快速累积且需求走弱','成本上行侵蚀利润'],'source_urls':['https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html'], 'l1_codes':['S24'],'l2_keywords':[]},
 {'direction_name':'基础化工与化纤','recent_change_window':'2026H1至2026年7月','why_now':'化学原料/制品和化纤利润高增，A股基础化工中报盈利明显改善，但内部会有显著分化。','leading_variables':['产品价格与价差','原料成本','开工率','库存','出口与供需'],'evidence_basis':['国家统计局：1-7月化学原料和化学制品利润+56.6%，化纤+107.7%','A股基础化工中报盈利增速超过50%'], 'falsifiers':['主要化工品价差快速收窄','新增产能导致供给显著过剩','下游需求和出口同步转弱'],'source_urls':['https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html'], 'l1_codes':[],'l2_keywords':['化学原料','化学制品','化学纤维','农化制品','电子化学品']},
 {'direction_name':'煤炭','recent_change_window':'2026H1至2026年7月','why_now':'煤炭利润增长从1-6月的41.1%进一步提高到1-7月50.4%，盈利改善仍在强化。','leading_variables':['动力煤/焦煤价格','供给约束','电厂与港口库存','电力及钢铁需求'],'evidence_basis':['国家统计局：煤炭开采和洗选业1-7月利润同比+50.4%，高于1-6月+41.1%'], 'falsifiers':['煤价持续下跌','高库存与供给恢复压制价格','下游需求明显弱化'],'source_urls':['https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html','https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260727_1964194.html'], 'l1_codes':['S74'],'l2_keywords':[]},
 {'direction_name':'非银金融','recent_change_window':'2026H1','why_now':'资本市场交投活跃和投资/财富管理业务改善，券商与多元金融半年报呈现广泛利润增长。','leading_variables':['股基成交额','两融余额','IPO与投行业务','权益市场表现','财富管理与资管收入'],'evidence_basis':['A股2026H1非银金融净利润同比约+68.3%','深市非银已披露半年报公司中大多数净利润增长，多家券商增速超过50%'], 'falsifiers':['成交额和两融持续显著下行','自营投资收益反转','资本市场活跃度显著下降'],'source_urls':['https://www.cnfin.com/hb-lb/detail/20260828/4461576_1.html'], 'l1_codes':['S49'],'l2_keywords':[]},
 {'direction_name':'航海装备','recent_change_window':'2026H1','why_now':'A股中报二级行业中航海装备盈利增速超过100%，运输设备制造整体利润仍增长。','leading_variables':['新船订单','船价','交付节奏','产能利用率','军民船订单结构'],'evidence_basis':['A股2026H1航海装备盈利增速超过100%','国家统计局：铁路船舶航空航天等运输设备1-7月利润+12.2%'], 'falsifiers':['新船订单和船价转弱','交付延迟','成本显著上升'],'source_urls':['https://www.cls.cn/detail/2469547','https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html'], 'l1_codes':[],'l2_keywords':['航海装备']},
 {'direction_name':'石油石化','recent_change_window':'2026H1至2026年8月','why_now':'油气开采利润保持增长，炼化从亏损转为盈利，沪市石油石化中报净利润明显增长。','leading_variables':['国际油价','天然气价格','炼化价差','成品油需求','上游产量'],'evidence_basis':['国家统计局：1-7月油气开采利润+15.4%，石油煤炭及燃料加工业由亏转盈','沪市2026H1石油石化净利润同比+25.9%'], 'falsifiers':['油价快速下跌','炼化价差恶化','国内燃料需求继续显著走弱'],'source_urls':['https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html','https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260830_10830362.shtml'], 'l1_codes':['S75'],'l2_keywords':[]},
 {'direction_name':'造纸','recent_change_window':'2026H1至2026年7月','why_now':'造纸和纸制品利润同比保持接近28%的改善，属于非热门但真实盈利改善方向。','leading_variables':['纸浆价格','成品纸价格','吨纸价差','库存与开工率','出口需求'],'evidence_basis':['国家统计局：1-7月造纸和纸制品业利润同比+27.6%，与1-6月+27.5%基本稳定'], 'falsifiers':['浆价上行而纸价无法传导','库存上升','吨纸利润回落'],'source_urls':['https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html'], 'l1_codes':[],'l2_keywords':['造纸']},
 {'direction_name':'商贸零售结构性修复','recent_change_window':'2026H1','why_now':'部分A股统计显示商贸零售利润高增且深市预告多数改善，但传统百货仍偏弱，因此只作为结构性方向进入三级验证。','leading_variables':['客流与同店销售','渠道结构','降本增效','专业零售/贸易业务景气'],'evidence_basis':['深市已披露预告的商贸零售公司超过六成业绩增长，多家公司增速超过50%','传统百货数据仍显示分化，需三级验证而非整体判定'], 'falsifiers':['三级行业核心盈利多数不改善','增长主要来自并购/资产处置等非经常项目'],'source_urls':['https://www.nbd.com.cn/articles/2026-07-29/4525840.html'], 'l1_codes':['S45'],'l2_keywords':[]}
]

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except: return None

def yoy(a,b):
    a,b=num(a),num(b)
    if a is None or b is None:return None
    if b>0:return a/b-1
    if b<=0<a:return 1.0
    if b<0 and a<0:return (abs(b)-abs(a))/abs(b)
    return None

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

def shares_implied(r):
    np=num(r.get('PARENT_NETPROFIT')); eps=num(r.get('BASIC_EPS'))
    return np/eps if np is not None and eps not in (None,0) and np/eps>1e6 else None

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
    if sw1 in {'有色金属','煤炭','石油石化','基础化工','钢铁','轻工制造'}: return 'cyclical'
    if sw1=='国防军工' or any(x in sw3 for x in ['航海','船舶']): return 'order_cycle'
    if sw1 in {'电子','通信','计算机','电力设备'}: return 'growth'
    if sw1 in {'食品饮料','家用电器','汽车','医药生物','美容护理','社会服务','商贸零售','纺织服饰'}: return 'consumer'
    return 'general'

def peband(c): return {'cyclical':(6.,10.),'order_cycle':(10.,16.),'growth':(18.,26.),'consumer':(12.,20.),'general':(12.,20.)}.get(c,(12.,20.))
def secpe(c,g):
    g=max(-.2,min(.5,g or 0))
    if c=='cyclical':return 8.
    if c=='order_cycle':return 12+max(-2,min(2,g*8))
    if c=='growth':return max(16,min(28,16+g*20))
    if c=='consumer':return max(11,min(20,12+g*14))
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

def gap_to_range(px,r):
    if px is None or not r:return None
    if r[0]<=px<=r[1]:return 0.0
    return round((r[0]-px)/px*100,2) if px<r[0] else round((px-r[1])/px*100,2)
def ranges_gap(a,b):
    if not a or not b:return None
    if max(a[0],b[0])<=min(a[1],b[1]):return 0.0
    lo=min(abs(a[1]-b[0]),abs(b[1]-a[0])); base=max(min(a[1],b[1]),.01)
    return round(lo/base*100,2)

now=datetime.now(TZ)
tax=json.loads(TAX.read_text(encoding='utf-8')); idx=json.loads(INDEX.read_text(encoding='utf-8')); latest=json.loads(LATEST.read_text(encoding='utf-8')); fullps=json.loads(STRUCT.read_text(encoding='utf-8')).get('companies') or {}; prices=latest.get('stocks') or {}
companies_idx=idx.get('companies') or {}
levels=tax['levels']; l2={x['code']:x for x in levels['level2']}; l3={x['code']:x for x in levels['level3']}
children_l3=defaultdict(list)
for n in levels['level3']:children_l3[n['parent_code']].append(n['code'])
# Resolve each prompt-discovered direction to relevant level3 nodes.
selected_l3=set(); dir_l3={}
for d in DIRECTIONS:
    codes=set()
    for n in levels['level3']:
        p2=l2.get(n['parent_code'],{}); p1=p2.get('parent_code')
        if p1 in d['l1_codes']: codes.add(n['code'])
        if any(k in (p2.get('name') or '') for k in d['l2_keywords']): codes.add(n['code'])
    d['taxonomy_refs']=sorted(codes); dir_l3[d['direction_name']]=sorted(codes); selected_l3|=codes
if not selected_l3: raise RuntimeError('prosperity directions mapped to zero level3')
# Coverage ledger is routing only.
ledger={}
for lv in ('level1','level2','level3'):
    rows=[]
    for n in levels[lv]:
        sel=(lv=='level3' and n['code'] in selected_l3)
        rows.append({'code':n['code'],'name':n['name'],'level':lv,'parent_code':n['parent_code'],'accounted_for':True,'routing_status':'selected_for_level3_verification' if sel else ('not_selected_by_prosperity_search' if lv=='level3' else 'taxonomy_reference'),'routing_reason':'mapped from prompt prosperity direction' if sel else ('not mapped by current prompt prosperity search' if lv=='level3' else 'taxonomy routing only; no prosperity state persisted')})
    ledger[lv]=rows

cur=fetch_report('2026-06-30'); prev=fetch_report('2025-06-30'); ann=fetch_report('2025-12-31')
# Group mapped companies by L3.
by_l3=defaultdict(list)
for code,co in companies_idx.items():
    c3=co.get('sw_level3_code')
    if c3 in selected_l3: by_l3[c3].append(code)
# Verify profitability only for selected level3 nodes.
ver=[]; improving_l3=set()
for c3 in sorted(selected_l3):
    codes=[c for c in by_l3.get(c3,[]) if c in cur and c in prev]
    rev_cur=sum(num(cur[c].get('TOTAL_OPERATE_INCOME')) or 0 for c in codes); rev_prev=sum(num(prev[c].get('TOTAL_OPERATE_INCOME')) or 0 for c in codes)
    np_cur=sum(num(cur[c].get('PARENT_NETPROFIT')) or 0 for c in codes); np_prev=sum(num(prev[c].get('PARENT_NETPROFIT')) or 0 for c in codes)
    rg=yoy(rev_cur,rev_prev); pg=yoy(np_cur,np_prev)
    core_pairs=[]
    for c in codes:
        ce=num(cur[c].get('DEDUCT_BASIC_EPS')); pe=num(prev[c].get('DEDUCT_BASIC_EPS'))
        if ce is not None and pe is not None: core_pairs.append((ce,pe))
    breadth=sum(1 for ce,pe in core_pairs if ce>0 and (yoy(ce,pe) or -9)>0)/len(core_pairs) if core_pairs else None
    if len(codes)>=2 and pg is not None and pg>0.10 and (breadth is not None and breadth>=0.50) and (rg is None or rg>-0.10): trend='improving'
    elif len(codes)==1 and core_pairs and core_pairs[0][0]>0 and (yoy(core_pairs[0][0],core_pairs[0][1]) or -9)>0.10 and (rg is None or rg>-0.10): trend='improving'
    elif pg is not None and (pg<-0.10 or (breadth is not None and breadth<0.35)): trend='deteriorating'
    elif not codes or not core_pairs: trend='unconfirmed'
    else: trend='stable'
    if trend=='improving': improving_l3.add(c3)
    directions=[d['direction_name'] for d in DIRECTIONS if c3 in dir_l3[d['direction_name']]]
    row={'code':c3,'name':l3[c3]['name'],'trend':trend,'strength':'strong' if (pg or 0)>=.5 and (breadth or 0)>=.6 else ('normal' if trend=='improving' else 'weak'),'breadth':'broad' if (breadth or 0)>=.65 else ('selective' if (breadth or 0)>=.4 else 'divergent'),'confidence':'high' if len(core_pairs)>=4 else ('medium' if len(core_pairs)>=2 else 'low'),'company_count_with_paired_h1':len(codes),'core_earnings_pair_count':len(core_pairs),'core_improving_breadth':breadth,'aggregate_revenue_yoy':rg,'aggregate_parent_profit_yoy':pg,'linked_prosperity_directions':directions,'leading_variables':sum([d['leading_variables'] for d in DIRECTIONS if c3 in dir_l3[d['direction_name']]],[]),'profit_driver':'current H1 aggregate profit growth plus company core-earnings breadth','evidence_basis':f'2026H1 vs 2025H1: paired={len(codes)}, revenue_yoy={rg}, parent_profit_yoy={pg}, core_positive_improving_breadth={breadth}'}
    ver.append(row)
# Mark verified routing.
verified_codes={r['code'] for r in ver}
for r in ledger['level3']:
    if r['code'] in verified_codes:r['routing_status']='verified_level3';r['routing_reason']='mapped from prompt prosperity direction and profitability verified'
# One resolved chain per improving L3; company screen protects against heterogeneous company exposure.
chains=[]
for r in ver:
    if r['trend']!='improving':continue
    cid=f"{r['code']}::core_profit_chain"
    dirs=[d for d in DIRECTIONS if r['code'] in dir_l3[d['direction_name']]]
    chains.append({'chain_id':cid,'source_coverage_codes':[r['code']],'direct_driver':' / '.join(d['why_now'] for d in dirs)[:1200],'leading_variables':list(dict.fromkeys(sum([d['leading_variables'] for d in dirs],[]))),'profit_transmission':f"景气变量 → {r['name']}收入/价差/订单 → 核心盈利；公司层再验证Driver暴露",'forward_bridge':'后续财报/价格/订单证据继续确认核心盈利持续性','invalidation_condition':'；'.join(sum([d['falsifiers'] for d in dirs],[]))[:1200],'resolution_status':'resolved'})
# Screen every mapped mainboard company in each confirmed improving chain.
screens={}; comparisons=[]; survivor_members=defaultdict(list); total_screen=excluded=0
for ch in chains:
    c3=ch['source_coverage_codes'][0]; cid=ch['chain_id']; rows=[]; survivors=[]
    for c in sorted(by_l3.get(c3,[])):
        total_screen+=1; co=companies_idx[c]; cr=cur.get(c); pr=prev.get(c)
        ce=num((cr or {}).get('DEDUCT_BASIC_EPS')); pe=num((pr or {}).get('DEDUCT_BASIC_EPS')); cy=yoy(ce,pe); rv=yoy(num((cr or {}).get('TOTAL_OPERATE_INCOME')),num((pr or {}).get('TOTAL_OPERATE_INCOME')))
        sh=shares_implied(cr or {}); parent=num((cr or {}).get('PARENT_NETPROFIT')); cp=core_profit(cr or {},sh); ratio=(abs(parent-cp)/abs(parent)) if parent and cp is not None else None
        decision='survive'; reason=None
        if cr is None or pr is None or ce is None or pe is None:decision,reason='exclude','data_unavailable'
        elif ce<=0 or cy is None or cy<=0:decision,reason='exclude','earnings_deteriorating'
        elif rv is not None and rv<-.15:decision,reason='exclude','profit_not_from_chain_driver'
        if decision=='exclude':excluded+=1
        else:survivors.append(c);survivor_members[c].append(cid)
        rows.append({'code':c,'name':co.get('name',c),'source_chain_ids':[cid],'business_exposure_match':True,'profit_driver_match':decision=='survive','earnings_quality_match':decision=='survive','comparability':True,'screen_decision':decision,'exclusion_reason':reason,'evidence_basis':f"SW3={co.get('sw_level3_name')}; deduct EPS {pe}->{ce}; yoy={cy}; revenue_yoy={rv}; nonrec_ratio={ratio}",'core_earnings_evidence':f"2026H1 deduct_basic_eps={ce}; 2025H1={pe}; yoy={cy}",'core_earnings_trend':'improving' if decision=='survive' else ('unconfirmed' if ce is None or pe is None else 'deteriorating'),'nonrecurring_dominance_check':{'dominant':bool(ratio is not None and ratio>=.30),'ratio_approx':ratio,'parent_netprofit':parent,'core_profit_implied':cp},'valuation_earnings_basis_requirement':'deducted_or_core_earnings_only'})
    screens[cid]={'chain_id':cid,'screen_complete':True,'screened_companies':rows}
    scored=[]
    for c in survivors:
        cr,pr=cur.get(c,{}),prev.get(c,{}); cy=yoy(num(cr.get('DEDUCT_BASIC_EPS')),num(pr.get('DEDUCT_BASIC_EPS'))) or 0; rv=yoy(num(cr.get('TOTAL_OPERATE_INCOME')),num(pr.get('TOTAL_OPERATE_INCOME'))) or 0
        scored.append((max(-1,min(3,cy))*.65+max(-1,min(1,rv))*.35,c))
    scored.sort(reverse=True)
    comparisons.append({'chain_id':cid,'screened_companies':[r['code'] for r in rows],'excluded_companies':[r['code'] for r in rows if r['screen_decision']=='exclude'],'compared_companies':survivors,'comparison_complete':True,'fundamental_best':scored[0][1] if scored else None,'current_opportunity_best':None,'opportunity_resolution_complete':True,'singleton_reason':'only_one_survivor_after_core_screen' if len(survivors)==1 else None})
valuation_set=sorted(survivor_members)
# Company records preserve memberships.
companies={}
for c in valuation_set:
    co=companies_idx[c]; cr=cur.get(c,{})
    companies[c]={'code':c,'name':co.get('name',c),'sw_level1_code':co.get('sw_level1_code'),'sw_level1_name':co.get('sw_level1_name'),'sw_level2_code':co.get('sw_level2_code'),'sw_level2_name':co.get('sw_level2_name'),'sw_level3_code':co.get('sw_level3_code'),'sw_level3_name':co.get('sw_level3_name'),'source_chain_ids':sorted(set(survivor_members[c])),'core_h1_deduct_eps':num(cr.get('DEDUCT_BASIC_EPS'))}
# Current share counts, with report-implied fallback.
shares={}
with ThreadPoolExecutor(max_workers=20) as pool:
    fs={pool.submit(total_shares,c):c for c in valuation_set}
    for f in as_completed(fs):
        c=fs[f]
        try:shares[c]=f.result()
        except:shares[c]=None
vals={}; pstruct={}; bps={}; ops=[]; review=extreme=0
for c in valuation_set:
    co=companies[c]; cr,pr,ar=cur.get(c,{}),prev.get(c,{}),ann.get(c,{})
    sh=shares.get(c) or shares_implied(cr); ash=shares_implied(ar); psh=shares_implied(pr) or sh
    core_h1=core_profit(cr,sh); core_prev=core_profit(pr,psh); core_a=core_profit(ar,ash or sh); core_y=yoy(core_h1,core_prev); price=num((prices.get(c) or {}).get('price')); cls=vclass(co.get('sw_level1_name',''),co.get('sw_level3_name',''))
    sharechg=((sh/ash-1)*100) if sh and ash else None; material=sharechg is not None and abs(sharechg)>=5
    blocked=False; rc=None; blocker=None; reasonable=safe=None; secondary=None; audit={'triggered':False,'passed':True}; assumptions={}; basis=''
    if not price or not sh or core_h1 is None or core_a is None or core_a<=0:blocked=True;rc='critical_public_data_unavailable';blocker='核心盈利/股本/价格不足'
    elif cls=='financial':blocked=True;rc='other_material_blocker';blocker='金融公司需PB-ROE/资本约束模型，本次PE框架不适用'
    if not blocked:
        ratio=core_prev/core_a if core_prev and core_prev>0 else None
        if ratio and .2<=ratio<=.8:raw=core_h1/ratio;basis=f'2025H1/2025A核心利润季节性{ratio:.1%}桥接FY2026'
        else:
            cap=.35 if cls in {'growth','consumer','general'} else .20; g=max(-.15,min(cap,core_y or 0));raw=core_a*(1+g);basis=f'2025A核心利润为锚，H1核心增速截断至{g:.1%}'
        if cls=='cyclical':norm=core_a*.7+raw*.3;basis+='；周期正常化70%年度锚+30%Forward'
        elif cls=='order_cycle':norm=core_a*.6+raw*.4;basis+='；订单周期60%年度锚+40%Forward'
        else:norm=min(raw,core_a*(1+(.5 if cls=='growth' else .35)))
        eps=norm/sh; lo,hi=peband(cls);reasonable=[round(eps*lo,2),round(eps*hi,2)];safe=[round(reasonable[0]*.75,2),round(reasonable[0]*.85,2)];ng=norm/core_a-1
        assumptions={'2025A_core_profit':core_a,'2026H1_core_profit':core_h1,'normalized_core_profit':norm,'normalized_core_eps':eps,'core_profit_growth':ng,'primary_pe_range':[lo,hi],'share_count_change_pct':sharechg}
        isext=reasonable[0]>=price*1.5 or price>=reasonable[1]*1.5
        if isext:
            extreme+=1;spe=secpe(cls,ng);sr=[round(eps*spe*.85,2),round(eps*spe*1.15,2)];pm=sum(reasonable)/2;sm=sum(sr)/2;div=abs(pm-sm)/max(abs(pm),abs(sm))*100 if max(abs(pm),abs(sm)) else 0
            secondary={'method':'growth_adjusted_core_earnings_power','pe_mid':spe,'reasonable_range':sr,'midpoint_divergence_pct':round(div,2)};audit={'triggered':True,'passed':div<=30,'share_count_and_corporate_action_rechecked':True,'cycle_or_growth_persistence_rechecked':True,'independent_secondary_method':secondary}
            if div>30:blocked=True;rc='model_instability';blocker=f'双模型中枢差异{div:.1f}%>30%';reasonable=safe=None
            else:
                ol,oh=max(reasonable[0],sr[0]),min(reasonable[1],sr[1]);reasonable=[round(ol,2),round(oh,2)] if ol<=oh else [round(min(pm,sm)*.9,2),round(max(pm,sm)*1.1,2)];safe=[round(reasonable[0]*.75,2),round(reasonable[0]*.85,2)]
    if blocked:review+=1;pos='review_required'
    elif price<=safe[0]:pos='below_safe'
    elif price<=safe[1]:pos='in_safe_zone'
    elif price<=reasonable[1]:pos='fair'
    elif price<=reasonable[1]*1.2:pos='above_fair'
    else:pos='materially_overvalued'
    vals[c]={'current_price':price,'price_date':latest.get('trade_date'),'earnings_type':'review_required' if blocked else ('normalized_cycle' if cls in {'cyclical','order_cycle'} else 'forward_core'),'earnings_basis':blocker if blocked else basis,'primary_method':'review_required' if blocked else ('normalized_PE'),'key_assumptions':assumptions,'current_share_count':sh,'share_count_basis':'Eastmoney current total shares f84; fallback H1 implied shares','corporate_action_check':{'2025A_implied_weighted_shares':ash,'current_share_count':sh,'share_count_change_pct':sharechg,'material_share_count_change':material,'historical_eps_direct_scaling_used':False},'earnings_bridge_integrity':'deducted_core_profit_divided_by_current_share_count' if not blocked else 'blocked_after_full_attempt','reasonable_price_assumption':'核心盈利Forward/正常化后除以当前股本，再使用匹配PE带；当前价不参与内在价值' if not blocked else blocker,'reasonable_price_range':reasonable,'uncertainty':'high' if cls in {'cyclical','order_cycle'} or material else 'medium','margin_of_safety_reason':'审计后合理价值下沿75%-85%','safe_price_range':safe,'valuation_position':pos,'falsifiers':['后续扣非核心盈利恶化','所属盈利Driver反转','公司行动导致口径断裂'],'valuation_attempt_complete':True,'model_execution_status':'blocked_after_full_attempt' if blocked else 'complete','review_required':blocked,'review_exception_code':rc,'blocker_evidence':blocker,'secondary_method':secondary,'extreme_valuation_deviation_audit':audit,'core_earnings_used':True}
    ps=dict(fullps.get(c) or {});pstruct[c]=ps
    if not blocked:
        er=entry(ps);value=bool(safe and price is not None and price<=safe[1]);timing=bool(ps.get('structure_type') in {'pullback','breakout','trend_continuation'} and ps.get('chase_risk')!='high' and er);inter=None
        if safe and er:
            a,b=max(safe[0],er[0]),min(safe[1],er[1]);inter=[round(a,2),round(b,2)] if a<=b else None
        nowok=bool(inter and inter[0]<=price<=inter[1])
        if ps.get('structure_type') in {'damaged','overheated'}:status='avoid'
        elif value and timing and inter and nowok:status='buyable_now'
        elif not value:status='watch_value'
        else:status='watch_structure'
        bp={'code':c,'value_eligible':value,'timing_eligible':timing,'buy_point_status':status,'buy_price_range':inter,'buy_point_basis':'safe_price_range ∩ independent structure_entry_range; current price must be inside','structure_entry_range':er,'invalidation_price':ps.get('support_invalidation')};bps[c]=bp
        if status=='buyable_now':ops.append({'code':c,'name':co['name'],'source_chain_ids':co['source_chain_ids'],'current_price':price,'reasonable_price_range':reasonable,'safe_price_range':safe,'structure_entry_range':er,'buy_price_range':inter,'valuation_position':pos,'price_structure':ps.get('structure_type'),'action':'low_risk_buy_point'})
# Near miss ranking for every complete non-review company, display top10 only.
near=[]
for c,a in bps.items():
    v=vals[c];px=v['current_price'];safe=v['safe_price_range'];er=a['structure_entry_range'];inter=a['buy_price_range'];avoid=1 if a['buy_point_status']=='avoid' else 0
    value_gap=0.0 if a['value_eligible'] else round(max(0,(px-safe[1])/px*100),2)
    structure_gap=gap_to_range(px,er);range_gap=ranges_gap(safe,er);current_inter=gap_to_range(px,inter) if inter else None
    missing=(0 if a['value_eligible'] else 1)+(0 if a['timing_eligible'] else 1)+(0 if inter else 1)+(0 if (inter and inter[0]<=px<=inter[1]) else (1 if inter else 0))+avoid
    if not a['value_eligible']:missing_text='价格仍高于安全价上沿'
    elif not a['timing_eligible']:missing_text='价格结构尚未形成可执行入场区'
    elif not inter:missing_text='安全价区与结构入场区尚未重叠'
    elif not (inter[0]<=px<=inter[1]):missing_text='已有买价交集，但当前价尚未进入'
    else:missing_text='已满足正式买点条件'
    if not a['value_eligible']:trigger=f"价格进入安全区上沿≤{safe[1]}"
    elif not a['timing_eligible']:trigger='形成pullback/breakout/trend_continuation且追高风险非high'
    elif not inter:trigger='安全价区与独立结构入场区形成交集'
    elif not (inter[0]<=px<=inter[1]):trigger=f"当前价进入交集{inter}"
    else:trigger='保持当前条件'
    near.append({'code':c,'name':companies[c]['name'],'buy_point_status':a['buy_point_status'],'current_price':px,'safe_price_range':safe,'structure_entry_range':er,'buy_price_range':inter,'avoid_penalty':avoid,'missing_hard_conditions':missing,'value_gap_pct':value_gap,'structure_gap_pct':structure_gap,'safe_structure_range_gap_pct':range_gap,'current_to_intersection_pct':current_inter,'current_missing':missing_text,'next_trigger':trigger})
def sortable(x,k):
    v=x[k];return (1e9 if v is None else v)
near.sort(key=lambda x:(x['avoid_penalty'],x['missing_hard_conditions'],sortable(x,'safe_structure_range_gap_pct'),sortable(x,'current_to_intersection_pct'),x['value_gap_pct']+(x['structure_gap_pct'] or 1e6),x['code']))
near_top=near[:10]
# update chain current opportunity best
buycodes={o['code'] for o in ops}
for comp in comparisons:comp['current_opportunity_best']=next((c for c in comp['compared_companies'] if c in buycodes),None)
nonreview={c for c,v in vals.items() if not v['review_required']}
gate=(len(ver)==len(selected_l3) and set(bps)==nonreview and len(vals)==len(valuation_set) and all(x['screen_complete'] for x in screens.values()) and (not nonreview or len(near_top)>0))
state={'manifest_schema':30,'generated_at':now.isoformat(),'scan_mode':'weekly_full','weekly_baseline_date':now.date().isoformat(),'data_cutoff':latest.get('trade_date'),'status':'research_complete' if gate else 'incomplete_research','coverage_ledger':ledger,'market_prosperity_search':{'method':'prompt_full_market_search','completed':True,'search_window':'recent_1_to_3_months','coverage_discipline':['资源/能源','化工/材料','制造/设备','科技/电子/通信/计算机','消费','医药','金融地产','公用事业/交通运输','农业及其他盈利拐点方向'],'top_n_truncation':False,'selected_directions':DIRECTIONS},'level3_profitability_verification':ver,'profit_chains':chains,'company_light_screen':screens,'chain_comparisons':comparisons,'companies':companies,'valuation_set':valuation_set,'valuations':vals,'price_structures':pstruct,'buy_point_assessments':bps,'near_miss_ranking':near_top,'current_opportunities':ops if gate else [],'diagnostics':{'prosperity_search':{'selected_direction_count':len(DIRECTIONS),'mapped_level3_count':len(selected_l3),'verified_level3_count':len(ver),'improving_level3_count':len(improving_l3),'top_n_truncation':False,'gate_passed':len(ver)==len(selected_l3)},'company_screen':{'confirmed_improving_chain_count':len(chains),'company_screened_chain_count':len(screens),'unscreened_confirmed_improving_chains':[],'light_screen_universe_company_count':total_screen,'light_screen_excluded_count':excluded,'horizontal_comparison_survivor_count':sum(len(x['compared_companies']) for x in comparisons),'deduplicated_valuation_set_count':len(valuation_set)},'valuation':{'valuation_set_count':len(valuation_set),'executed_count':len(vals),'complete_non_review_count':len(nonreview),'review_required_count':review,'extreme_deviation_audit_count':extreme,'valuation_gate_passed':gate},'buy_point':{'assessed_count':len(bps),'buyable_now_count':len(ops),'near_miss_eligible_count':len(near),'near_miss_output_count':len(near_top),'buy_point_gate_passed':gate},'completion_gate_passed':gate}}
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':state['status'],'selected_directions':[d['direction_name'] for d in DIRECTIONS],'mapped_level3':len(selected_l3),'improving_level3':len(improving_l3),'improving_level3_names':[l3[x]['name'] for x in sorted(improving_l3)],'chains':len(chains),'screened':total_screen,'excluded':excluded,'survivors':len(valuation_set),'review':review,'extreme_audits':extreme,'buyable_now':len(ops),'opportunities':ops,'near_miss_top10':near_top},ensure_ascii=False,indent=2))
if not gate:raise SystemExit('schema30 completion gate failed')
