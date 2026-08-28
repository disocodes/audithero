from __future__ import annotations
from datetime import time
from decimal import Decimal
import json,pandas as pd,numpy as np
from .money import money,effective_hourly_rate,line_amount

def _dt(v):
    x=pd.to_datetime(v,errors='coerce');return None if pd.isna(x) else x
def _emp_type(v):
    s=str(v or '').upper().replace('-','_').replace(' ','_')
    if 'CASUAL' in s:return 'CASUAL'
    if 'PART' in s:return 'PART_TIME'
    if 'FULL' in s:return 'FULL_TIME'
    return 'UNKNOWN'
def _effective_row(df,eid,at_date,start_col,end_col=None):
    if df is None or df.empty:return None
    q=df[df.employee_id.astype(str)==str(eid)].copy();q['_s']=pd.to_datetime(q[start_col],errors='coerce');q=q[q['_s']<=pd.to_datetime(at_date)]
    if end_col and end_col in q.columns:q['_e']=pd.to_datetime(q[end_col],errors='coerce');q=q[q['_e'].isna()|(q['_e']>=pd.to_datetime(at_date))]
    return None if q.empty else q.sort_values('_s',ascending=False).iloc[0].to_dict()
def _split(start,end,break_minutes=0):
    start=pd.to_datetime(start);end=pd.to_datetime(end);cuts=[start];m=start.normalize()+pd.Timedelta(days=1)
    while m<end:cuts.append(m);m+=pd.Timedelta(days=1)
    cuts.append(end);out=[]
    for a,b in zip(cuts[:-1],cuts[1:]):out.append({'date':a.date(),'hours':(b-a).total_seconds()/3600})
    if len(out)==1:out[0]['hours']=max(0,out[0]['hours']-float(break_minutes or 0)/60)
    return out
def _day_type(d,state,holidays):
    if holidays is not None and not holidays.empty:
        h=holidays.copy();h['_d']=pd.to_datetime(h.holiday_date,errors='coerce').dt.date
        if ((h._d==d)&(h.state.astype(str).str.upper()==str(state).upper())).any():return 'PUBLIC_HOLIDAY'
    return 'SATURDAY' if d.weekday()==5 else 'SUNDAY' if d.weekday()==6 else 'WEEKDAY'
def _shift_type(start,end):
    start=pd.to_datetime(start);end=pd.to_datetime(end)
    if start.weekday()>4:return 'NONE'
    if start.time()<time(6):return 'NIGHT'
    if end.date()>start.date():return 'NIGHT'
    if end.time()>time(20):return 'AFTERNOON'
    return 'NONE'
def _mult(c,emp_type,day_type,shift_type):
    m=float(c['ordinary_penalties'][emp_type][day_type])
    if day_type=='WEEKDAY' and shift_type in ('AFTERNOON','NIGHT'):m=(1.25 if emp_type=='CASUAL' else 1.0)+float(c['shiftwork'][shift_type]['loading'])
    return m
def _minimum(c,work_group,emp_type):
    for r in c['minimum_engagement']:
        if r['work_group']==work_group and emp_type in r['employment_types']:return float(r['hours']),r['clause']
    return 0,None

def assign_pay_periods(timesheets,pay_runs):
    """Attach pay-period dates from Payroll API pay runs. Ambiguous overlapping schedules stay unassigned."""
    df=timesheets.copy();df['pay_period_start']=None;df['pay_period_end']=None;df['pay_run_id']=None
    if not pay_runs:return df
    def first(r,*keys):
        for k in keys:
            if isinstance(r,dict) and r.get(k) not in (None,''):return r[k]
    periods=[]
    for r in pay_runs:
        ps=_dt(first(r,'payPeriodStarting','PayPeriodStarting','payPeriodStart','startDate'));pe=_dt(first(r,'payPeriodEnding','PayPeriodEnding','payPeriodEnd','endDate'));rid=first(r,'id','Id','payRunId','PayRunId')
        if ps is not None and pe is not None:periods.append((ps.normalize(),pe.normalize(),rid))
    for idx,row in df.iterrows():
        s=_dt(row.get('start_datetime'))
        if s is None:continue
        hits=[p for p in periods if p[0].date()<=s.date()<=p[1].date()]
        if len(hits)==1:
            ps,pe,rid=hits[0];df.at[idx,'pay_period_start']=ps;df.at[idx,'pay_period_end']=pe;df.at[idx,'pay_run_id']=rid
        elif len(hits)>1:
            df.at[idx,'pay_period_mapping_status']='AMBIGUOUS_PAY_SCHEDULE'
    return df

def calculate_entitlements(employees,employment_history,classifications,timesheets,holidays,lib):
    if timesheets is None or timesheets.empty:return pd.DataFrame()
    emp_index={str(r.employee_id):r.to_dict() for _,r in employees.iterrows()};rows=[]
    for _,ts0 in timesheets.iterrows():
        ts=ts0.to_dict();flags=[];eid=str(ts.get('employee_id'));emp=emp_index.get(eid);start=_dt(ts.get('start_datetime'));end=_dt(ts.get('end_datetime'))
        if not emp or start is None or end is None or end<=start:
            rows.append({'timesheet_id':ts.get('timesheet_id'),'employee_id':eid,'entitlement_status':'REQUIRES_REVIEW','review_flags':'EMPLOYEE_OR_SHIFT_INVALID'});continue
        if ts.get('pay_period_mapping_status')=='AMBIGUOUS_PAY_SCHEDULE':flags.append('AMBIGUOUS_PAY_SCHEDULE')
        eh=_effective_row(employment_history,eid,start,'start_date','end_date');emp_type=_emp_type((eh or {}).get('employment_type') or emp.get('employment_type_current'))
        if emp_type=='UNKNOWN':flags.append('EMPLOYMENT_TYPE_HISTORY_MISSING')
        cls=_effective_row(classifications,eid,start,'effective_from');code=(cls or {}).get('classification_code')
        if not code:flags.append('SCHADS_CLASSIFICATION_MAPPING_MISSING')
        pp_start=_dt(ts.get('pay_period_start'));reference=pp_start if pp_start is not None else start
        if pp_start is None:flags.append('PAY_PERIOD_START_MISSING_RATE_VERSION_MAY_BE_WRONG')
        rate,pack=lib.rate(code,reference) if code else (None,None);conditions=lib.conditions(reference)
        if not rate:flags.append('RATE_PACK_OR_CLASSIFICATION_MISSING')
        if not conditions:flags.append('CONDITION_PACK_MISSING')
        base=float(rate['base_hourly_rate']) if rate else None;state=ts.get('location_state') or emp.get('state');work_group=ts.get('work_group') or emp.get('work_group') or 'DISABILITY_SERVICES'
        if not state:flags.append('STATE_MISSING_PUBLIC_HOLIDAY_CHECK_INCOMPLETE')
        break_minutes=float(ts.get('unpaid_break_minutes') or 0)
        if not break_minutes and ts.get('break_units') not in (None,''):
            # EH break_units may be expressed in hours; tenant validation is still required.
            try:break_minutes=float(ts.get('break_units') or 0)*60
            except Exception:break_minutes=0
        segs=_split(start,end,break_minutes);worked=sum(s['hours'] for s in segs);stype=_shift_type(start,end);expected=Decimal('0');evidence=[]
        if base is not None and conditions and emp_type in ('FULL_TIME','PART_TIME','CASUAL'):
            for seg in segs:
                dt=_day_type(seg['date'],state,holidays);mult=_mult(conditions,emp_type,dt,stype);er=effective_hourly_rate(base,mult);amt=line_amount(seg['hours'],er);expected+=amt;evidence.append({'component':'ORDINARY_OR_PENALTY','date':str(seg['date']),'hours':round(seg['hours'],4),'day_type':dt,'shift_type':stype,'base_rate':base,'multiplier':mult,'effective_hourly_rate':float(er),'amount':float(amt),'rate_pack_id':pack['rate_pack_id']})
            mh,clause=_minimum(conditions,work_group,emp_type)
            if mh and worked<mh:
                dt=_day_type(segs[0]['date'],state,holidays);mult=_mult(conditions,emp_type,dt,stype);er=effective_hourly_rate(base,mult);extra=mh-worked;amt=line_amount(extra,er);expected+=amt;evidence.append({'component':'MINIMUM_ENGAGEMENT_TOPUP','hours':extra,'amount':float(amt),'clause':clause})
            if worked>10:flags.append('DAILY_OVERTIME_REVIEW')
            if bool(ts.get('is_sleepover')):
                a,ap=lib.allowance('sleepover',reference)
                if a:expected+=money(a['amount']);evidence.append({'component':'SLEEPOVER_ALLOWANCE','amount':float(money(a['amount'])),'allowance_pack_id':ap['allowance_pack_id']})
                if float(ts.get('sleepover_active_minutes') or 0)>0:flags.append('SLEEPOVER_ACTIVE_WORK_NEEDS_SEPARATE_RECORD')
                if conditions['sleepover'].get('surrounding_work_is_one_shift') and not ts.get('sleepover_group_id'):flags.append('SLEEPOVER_2026_CONTINUOUS_SHIFT_GROUPING_MISSING')
            if worked>float(conditions['meal_break']['review_if_shift_gt_hours_and_no_break']) and break_minutes==0:flags.append('MEAL_BREAK_REVIEW')
        rows.append({'timesheet_id':ts.get('timesheet_id'),'employee_id':eid,'employee_name':emp.get('employee_name'),'employment_type':emp_type,'classification_code':code,'work_group':work_group,'state':state,'pay_period_start':pp_start,'pay_period_end':_dt(ts.get('pay_period_end')),'award_reference_date':reference,'shift_start':start,'shift_end':end,'worked_hours':round(worked,4),'base_hourly_rate':base,'expected_amount':float(money(expected)) if base is not None and conditions else None,'entitlement_status':'REQUIRES_REVIEW' if flags else 'CALCULATED','review_flags':'; '.join(sorted(set(flags))),'calculation_evidence':json.dumps(evidence,default=str,separators=(',',':'))})
    return pd.DataFrame(rows)

def reconcile_pay_periods(entitlements,payroll_lines,mapping,tolerance=.05):
    if entitlements is None or entitlements.empty:return pd.DataFrame()
    e=entitlements.copy();e['expected_amount']=pd.to_numeric(e.expected_amount,errors='coerce');cols=['employee_id','employee_name','pay_period_start','pay_period_end'];exp=e.groupby(cols,dropna=False).agg(expected_amount=('expected_amount','sum'),shift_count=('timesheet_id','count'),entitlement_review_count=('entitlement_status',lambda s:int((s=='REQUIRES_REVIEW').sum()))).reset_index()
    if payroll_lines is None or payroll_lines.empty:exp['actual_auditable_amount']=None;exp['variance_actual_minus_expected']=None;exp['unmapped_pay_categories']='ACTUAL_PAY_UNAVAILABLE';exp['status']='ENTITLEMENT_ONLY';return exp
    p=payroll_lines.copy();p['pay_period_start']=pd.to_datetime(p.pay_period_start,errors='coerce');p['pay_period_end']=pd.to_datetime(p.pay_period_end,errors='coerce');p['amount']=pd.to_numeric(p.amount,errors='coerce').fillna(0)
    def treatment(r):
        for k in [str(r.get('pay_category_id') or ''),str(r.get('pay_category') or '')]:
            if k in mapping:return mapping[k].get('audit_treatment') if isinstance(mapping[k],dict) else mapping[k]
        return 'UNMAPPED'
    p['audit_treatment']=p.apply(treatment,axis=1);rows=[]
    for keys,g in p.groupby(['employee_id','pay_period_start','pay_period_end'],dropna=False):
        aud=g[g.audit_treatment.isin(['AUDITABLE_WORK','ALLOWANCE'])];unmapped=sorted(set(g.loc[g.audit_treatment=='UNMAPPED','pay_category'].astype(str)));rows.append({'employee_id':str(keys[0]),'pay_period_start':keys[1],'pay_period_end':keys[2],'actual_auditable_amount':round(float(aud.amount.sum()),2),'unmapped_pay_categories':'; '.join(unmapped)})
    out=exp.merge(pd.DataFrame(rows),on=['employee_id','pay_period_start','pay_period_end'],how='left');out['variance_actual_minus_expected']=(pd.to_numeric(out.actual_auditable_amount,errors='coerce')-pd.to_numeric(out.expected_amount,errors='coerce')).round(2)
    def status(r):
        if int(r.entitlement_review_count)>0 or r.get('unmapped_pay_categories'):return 'REQUIRES_REVIEW'
        if pd.isna(r.actual_auditable_amount):return 'ACTUAL_PAY_UNAVAILABLE'
        return 'UNDERPAID' if r.variance_actual_minus_expected<-tolerance else 'OVERPAID' if r.variance_actual_minus_expected>tolerance else 'COMPLIANT'
    out['status']=out.apply(status,axis=1);return out
