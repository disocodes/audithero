from __future__ import annotations
import json
from datetime import time
from decimal import Decimal
import pandas as pd
import numpy as np

from .money import money,effective_hourly_rate,line_amount
from .roster_overtime import _day_type,_ot_multiplier


def _dt(v):
    if v is None or v=='':return None
    x=pd.to_datetime(v,errors='coerce')
    return None if pd.isna(x) else x


def _bool(v):
    if isinstance(v,bool):return v
    return str(v).strip().lower() in {'1','true','yes','y'}


def calculate_supplemental_events(events,employees,classifications,holidays,lib):
    if events is None or events.empty:return pd.DataFrame()
    emp_index={str(r['employee_id']):r.to_dict() for _,r in employees.iterrows()};rows=[]
    for _,ev0 in events.iterrows():
        ev=ev0.to_dict();flags=[];evidence=[];eid=str(ev.get('employee_id'));emp=emp_index.get(eid,{})
        start=_dt(ev.get('start_datetime'));end=_dt(ev.get('end_datetime'));ref=_dt(ev.get('pay_period_start')) or start
        event_type=str(ev.get('event_type') or '').upper();code=ev.get('classification_code')
        if not code and classifications is not None and not classifications.empty and start is not None:
            q=classifications[classifications['employee_id'].astype(str)==eid].copy();q['_s']=pd.to_datetime(q['effective_from'],errors='coerce');q=q[q['_s']<=start]
            if not q.empty:code=q.sort_values('_s',ascending=False).iloc[0].get('classification_code')
        rate,_=lib.rate(code,ref) if code and ref is not None else (None,None);cond=lib.conditions(ref) if ref is not None else None;base=float(rate['base_hourly_rate']) if rate else None
        emp_type=str(ev.get('employment_type') or emp.get('employment_type_current') or '').upper().replace(' ','_')
        if 'CASUAL' in emp_type:emp_type='CASUAL'
        elif 'PART' in emp_type:emp_type='PART_TIME'
        elif 'FULL' in emp_type:emp_type='FULL_TIME'
        work_group=str(ev.get('work_group') or emp.get('work_group') or 'DISABILITY_SERVICES');state=ev.get('state') or emp.get('state');expected=Decimal('0')

        if event_type=='ON_CALL':
            if ref is None:flags.append('ON_CALL_REFERENCE_DATE_MISSING')
            else:
                day=_day_type(ref.date(),state,holidays);key='on_call_weekday' if day=='WEEKDAY' else 'on_call_other';a,_=lib.allowance(key,ref)
                if a:expected+=money(a['amount']);evidence.append({'component':'ON_CALL_ALLOWANCE','key':key,'amount':float(money(a['amount'])),'clause':'20.11'})
                else:flags.append('ON_CALL_ALLOWANCE_MISSING')
        elif event_type=='RECALL_WORKPLACE':
            if base is None or cond is None or start is None:flags.append('RECALL_FACTS_OR_RATE_MISSING')
            else:
                hours=max(2.0,float(ev.get('hours') or ((end-start).total_seconds()/3600 if end is not None else 0)));day=_day_type(start.date(),state,holidays);mult=_ot_multiplier(cond,emp_type,work_group,day,0);er=effective_hourly_rate(base,mult);amt=line_amount(hours,er);expected+=amt;evidence.append({'component':'RECALL_WORKPLACE','paid_hours':hours,'rate':float(er),'amount':float(amt),'clause':'28.4'})
        elif event_type=='SLEEPOVER_ACTIVE':
            if base is None or cond is None or start is None:flags.append('SLEEPOVER_ACTIVE_FACTS_OR_RATE_MISSING')
            else:
                actual=float(ev.get('hours') or ((end-start).total_seconds()/3600 if end is not None else 0));hours=max(float(cond['sleepover']['active_work_minimum_hours']),actual);day=_day_type(start.date(),state,holidays);mult=_ot_multiplier(cond,emp_type,work_group,day,0);er=effective_hourly_rate(base,mult);amt=line_amount(hours,er);expected+=amt;evidence.append({'component':'SLEEPOVER_ACTIVE_WORK','actual_hours':actual,'paid_hours':hours,'rate':float(er),'amount':float(amt),'clause':'25.7'})
        elif event_type=='REMOTE_WORK':
            if base is None or cond is None or start is None:flags.append('REMOTE_WORK_FACTS_OR_RATE_MISSING')
            else:
                actual=float(ev.get('hours') or ((end-start).total_seconds()/3600 if end is not None else 0));on_call=_bool(ev.get('on_call'));meeting=_bool(ev.get('training_or_meeting'));minimum=1.0 if meeting or not on_call else .5 if start.time()>=time(22) or start.time()<time(6) else .25;hours=np.ceil(max(actual,minimum)*4-1e-9)/4;day=_day_type(start.date(),state,holidays)
                if day=='WEEKDAY' and time(6)<=start.time()<time(20):mult=1.25 if emp_type=='CASUAL' else 1.0
                elif day=='SATURDAY':mult=1.75 if emp_type=='CASUAL' else 1.5
                elif day=='SUNDAY':mult=2.25 if emp_type=='CASUAL' else 2.0
                elif day=='PUBLIC_HOLIDAY':mult=2.75 if emp_type=='CASUAL' else 2.5
                else:
                    if hours>2:flags.append('REMOTE_WORK_OVER_2H_BAND_ALLOCATION_REVIEW')
                    mult=1.75 if emp_type=='CASUAL' else 1.5
                er=effective_hourly_rate(base,mult);amt=line_amount(hours,er);expected+=amt;evidence.append({'component':'REMOTE_WORK','actual_hours':actual,'paid_hours':hours,'multiplier':mult,'amount':float(amt),'clause':'25.10'})
        elif event_type=='CARE_24H':
            if base is None:flags.append('CARE_24H_RATE_MISSING')
            elif not str(code or '').startswith('HC-'):flags.append('CARE_24H_HOME_CARE_CLASSIFICATION_REQUIRED')
            else:
                hours=float(ev.get('hours') or 8);ordinary=min(hours,8.0);er=effective_hourly_rate(base,1.55);amt=line_amount(ordinary,er);expected+=amt;evidence.append({'component':'24_HOUR_CARE','hours':ordinary,'multiplier':1.55,'amount':float(amt),'clause':'25.8'});flags.append('CARE_24H_REPLACES_STANDARD_SHIFT_REVIEW')
                if hours>8:flags.append('CARE_24H_OVERTIME_BEYOND_8H_REVIEW')
        elif event_type=='BROKEN_SHIFT_ALLOWANCE':
            if cond is None:flags.append('BROKEN_SHIFT_RULE_MISSING')
            else:
                n=int(float(ev.get('unpaid_breaks') or 0))
                if n not in (1,2):flags.append('BROKEN_SHIFT_BREAK_COUNT_INVALID')
                else:
                    if work_group not in cond['broken_shift']['eligible_work_groups']:flags.append('BROKEN_SHIFT_WORK_GROUP_NOT_ELIGIBLE')
                    if n==2 and not _bool(ev.get('two_breaks_agreed')):flags.append('BROKEN_SHIFT_TWO_BREAK_AGREEMENT_REQUIRED')
                    key='broken_shift_1_break' if n==1 else 'broken_shift_2_breaks';a,_=lib.allowance(key,ref)
                    if a:expected+=money(a['amount']);evidence.append({'component':'BROKEN_SHIFT_ALLOWANCE','breaks':n,'amount':float(money(a['amount'])),'clause':'20.12'})
                    else:flags.append('BROKEN_SHIFT_ALLOWANCE_MISSING')
                    if float(ev.get('span_hours') or 0)>float(cond['broken_shift']['max_span_hours']):flags.append('BROKEN_SHIFT_BEYOND_12H_DOUBLE_TIME_REVIEW')
                    if not _bool(ev.get('period_minimums_verified')):flags.append('BROKEN_SHIFT_PERIOD_MINIMUMS_NOT_VERIFIED')
        elif event_type=='HIGHER_DUTIES':
            higher=ev.get('higher_classification_code');hr,_=lib.rate(higher,ref) if higher else (None,None)
            if base is None or not hr:flags.append('HIGHER_DUTIES_RATE_MISSING')
            else:
                higher_base=float(hr['base_hourly_rate']);hours=float(ev.get('hours') or 0);shift_hours=float(ev.get('shift_hours') or hours)
                if str(code or '').startswith('HC-'):paid_hours=shift_hours if hours>2 else hours
                else:
                    days=int(float(ev.get('consecutive_working_days') or 0));paid_hours=hours if days>=5 else 0
                    if days<5:flags.append('HIGHER_DUTIES_OTHER_EMPLOYEE_UNDER_5_DAYS')
                if paid_hours>0:
                    diff=money(higher_base-base);amt=line_amount(paid_hours,diff);expected+=amt;evidence.append({'component':'HIGHER_DUTIES_DIFFERENTIAL','hours':paid_hours,'base_difference':float(diff),'amount':float(amt),'clause':'20.6'})
        else:flags.append('UNKNOWN_SUPPLEMENTAL_EVENT_TYPE')

        rows.append({'event_id':ev.get('event_id'),'employee_id':eid,'employee_name':emp.get('employee_name'),'event_type':event_type,'pay_period_start':_dt(ev.get('pay_period_start')),'pay_period_end':_dt(ev.get('pay_period_end')),'expected_adjustment':float(money(expected)),'event_status':'REQUIRES_REVIEW' if flags else 'CALCULATED','review_flags':'; '.join(sorted(set(flags))),'calculation_evidence':json.dumps(evidence,default=str,separators=(',',':'))})
    return pd.DataFrame(rows)


def merge_event_adjustments_into_entitlements(detail,event_adjustments):
    if event_adjustments is None or event_adjustments.empty:return detail
    rows=[]
    for _,r in event_adjustments.iterrows():
        rows.append({'timesheet_id':f"EVENT:{r.get('event_id')}",'employee_id':r.get('employee_id'),'employee_name':r.get('employee_name'),'employment_type':None,'classification_code':None,'work_group':None,'state':None,'pay_period_start':r.get('pay_period_start'),'pay_period_end':r.get('pay_period_end'),'award_reference_date':r.get('pay_period_start'),'shift_start':pd.NaT,'shift_end':pd.NaT,'worked_hours':0.0,'base_hourly_rate':None,'expected_amount':r.get('expected_adjustment') if r.get('event_status')=='CALCULATED' else None,'entitlement_status':'REQUIRES_REVIEW' if r.get('event_status')=='REQUIRES_REVIEW' else 'CALCULATED','review_flags':r.get('review_flags'),'calculation_evidence':r.get('calculation_evidence')})
    ev=pd.DataFrame(rows)
    return pd.concat([detail,ev],ignore_index=True,sort=False) if detail is not None and not detail.empty else ev
