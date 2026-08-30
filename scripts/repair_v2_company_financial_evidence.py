from __future__ import annotations

import json, math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMPANY=ROOT/'data/research/v2/company_research.json'
TZ=ZoneInfo('Asia/Shanghai')


def load(p): return json.loads(p.read_text(encoding='utf-8'))
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def em_symbol(code): return f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
def date_key(v): return str(v)[:10]

def rows_by_date(df):
    if df is None or getattr(df,'empty',True): return {}
    out={}
    for _,r in df.iterrows():
        d=date_key(r.get('REPORT_DATE'))
        if d and d!='None': out[d]=dict(r)
    return out

def fallback_sina(ak,code):
    df=ak.stock_financial_analysis_indicator(symbol=code,start_year='2025')
    if df is None or df.empty:return {}
    out={}
    for _,r in df.iterrows():
        d=date_key(r.get('日期'))
        if not d or d=='None':continue
        out[d]={
            'REPORT_DATE':d,
            'EPSKCJB':r.get('扣除非经常性损益后的每股收益（元）'),
            'KCFJCXSYJLR':r.get('扣除非经常性损益后的净利润（元）'),
            'MGJYXJJE':r.get('每股经营性现金流（元）'),
            'NON_MAIN_RATIO':r.get('非主营比重'),
            'MAIN_PROFIT_RATIO':r.get('主营利润比重'),
            'CASH_TO_PROFIT_RATIO':r.get('经营现金净流量与净利润的比率(%)')
        }
    return out

def fetch_financial_rows(ak,code):
    errors=[]
    try:
        df=ak.stock_financial_analysis_indicator_em(symbol=em_symbol(code),indicator='按报告期')
        rows=rows_by_date(df)
        if rows:return rows,'eastmoney_financial_analysis',errors
        errors.append('eastmoney_empty')
    except Exception as exc: errors.append(f'eastmoney:{type(exc).__name__}:{exc}')
    try:
        rows=fallback_sina(ak,code)
        if rows:return rows,'sina_financial_indicator',errors
        errors.append('sina_empty')
    except Exception as exc: errors.append(f'sina:{type(exc).__name__}:{exc}')
    return {},None,errors

def closest(rows,target):
    return rows.get(target) or {}

def latest_at_or_before(rows,ref):
    ds=sorted(d for d in rows if d<=ref)
    return rows[ds[-1]] if ds else {}

def ttm_eps(rows):
    h1=closest(rows,'2026-06-30'); fy=closest(rows,'2025-12-31'); h1p=closest(rows,'2025-06-30')
    a,b,c=num(h1.get('EPSKCJB')),num(fy.get('EPSKCJB')),num(h1p.get('EPSKCJB'))
    if None in (a,b,c):return None
    return b+a-c

def main():
    import akshare as ak
    payload=load(COMPANY); companies=payload.get('companies') or {}; selected=payload.get('selected_for_valuation_codes') or []
    ref=str(payload.get('reference_trade_date') or '')[:10]; errors={}; verified=0; production_ready=0; ttm_ready=0
    for code in selected:
        row=companies.get(code) or {}
        fin,source,errs=fetch_financial_rows(ak,code)
        if errs: errors[code]=errs
        latest=latest_at_or_before(fin,ref) if fin else {}
        ded_np=num(latest.get('KCFJCXSYJLR')); ded_eps=num(latest.get('EPSKCJB')); parent=num(latest.get('PARENTNETPROFIT'))
        if parent is None: parent=num((row.get('metrics') or {}).get('net_profit'))
        ocfps=num(latest.get('MGJYXJJE')); cash_to_rev=num(latest.get('JYXJLYYSR')); cash_to_profit=num(latest.get('CASH_TO_PROFIT_RATIO'))
        ded_yoy=num(latest.get('KCFJCXSYJLRTZ')); ded_qoq=num(latest.get('KFJLRGDHBZC')); non_main=num(latest.get('NON_MAIN_RATIO')); main_profit_ratio=num(latest.get('MAIN_PROFIT_RATIO'))
        one_off_share=None
        if parent not in (None,0) and ded_np is not None: one_off_share=(parent-ded_np)/abs(parent)*100
        recurring_positive=bool(ded_np is not None and ded_np>0 and ded_eps is not None and ded_eps>0)
        recurring_share_ok=bool(one_off_share is None or one_off_share<=35)
        cashflow_ok=bool((ocfps is not None and ocfps>=0) or (cash_to_rev is not None and cash_to_rev>=0) or (cash_to_profit is not None and cash_to_profit>=30))
        recurring_verified=bool(recurring_positive and recurring_share_ok)
        ttm=ttm_eps(fin) if fin else None
        if ttm is not None and ttm>0: ttm_ready+=1
        if recurring_verified: verified+=1
        evidence={
            'source':source,'report_date':date_key(latest.get('REPORT_DATE')) if latest else None,
            'deducted_net_profit':ded_np,'deducted_eps':ded_eps,'deducted_profit_yoy_pct':ded_yoy,'deducted_profit_qoq_pct':ded_qoq,
            'operating_cashflow_per_share':ocfps,'operating_cashflow_to_revenue_pct':cash_to_rev,'operating_cashflow_to_net_profit_pct':cash_to_profit,
            'one_off_share_of_parent_profit_pct':round(one_off_share,2) if one_off_share is not None else None,
            'non_main_profit_ratio_pct':non_main,'main_profit_ratio_pct':main_profit_ratio,'ttm_deducted_eps':round(ttm,4) if ttm is not None else None,
            'recurring_profit_verified':recurring_verified,'cashflow_quality_verified':cashflow_ok,
            'quality_rule':'扣非净利润/扣非EPS为正；一次性因素占归母利润原则上<=35%；现金流至少一项非负或经营现金/净利润>=30%。'
        }
        row['financial_evidence']=evidence
        if recurring_verified:
            row['recurring_profit_status']='verified_by_financial_statement'
            row['deducted_profit_verification_required']=False
        else:
            row['deducted_profit_verification_required']=True
        if ded_np is not None and ded_np<=0 and row.get('research_status')=='pass': row['research_status']='quality_review_required'
        if one_off_share is not None and one_off_share>50 and row.get('research_status')=='pass': row['research_status']='quality_review_required'
        ready=bool(row.get('research_status')=='pass' and row.get('forward_bridge_valid') and row.get('low_risk_eligible') and recurring_verified and cashflow_ok)
        row['production_evidence_ready']=ready
        if ready: production_ready+=1
        companies[code]=row
    payload['schema_version']=2; payload['generated_at']=datetime.now(TZ).isoformat(); payload['companies']=companies
    payload['research_status_counts']={s:sum(1 for x in companies.values() if x.get('research_status')==s) for s in sorted(set(x.get('research_status') for x in companies.values()))}
    payload['research_pass_codes']=sorted(c for c,x in companies.items() if x.get('research_status')=='pass')
    payload['quality_review_required_codes']=sorted(c for c,x in companies.items() if x.get('research_status')=='quality_review_required')
    payload['production_evidence_ready_codes']=sorted(c for c,x in companies.items() if x.get('production_evidence_ready'))
    payload['financial_evidence_summary']={'selected_count':len(selected),'recurring_profit_verified_count':verified,'ttm_deducted_eps_available_count':ttm_ready,'production_evidence_ready_count':production_ready,'source_error_count':len(errors),'source_errors':errors}
    payload['method_note']=str(payload.get('method_note') or '')+' Selected valuation candidates are automatically repaired with statement-level recurring-profit and cashflow evidence; TTM deducted EPS uses FY2025 + H1 2026 - H1 2025, never simple H1 annualization.'
    COMPANY.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','selected':len(selected),'recurring_verified':verified,'ttm_deducted_eps':ttm_ready,'production_evidence_ready':production_ready,'source_errors':len(errors)},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
