from __future__ import annotations
import json
from datetime import time
from decimal import Decimal
import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value
from .money import money, effective_hourly_rate, line_amount


def _dt(v):
    if v is None or v == '': return None
    x = parse_datetime_value(v)
    return None if pd.isna(x) else x


def _bool(v):
    if isinstance(v, bool): return v
    return str(v).strip().lower() in {'1','true','yes','y'}


def _day_type(d, state, holidays, location_key=None):
    if holidays is not None and not holidays.empty:
        h=holidays.copy();h['_d']=parse_datetime_series(h['holiday_date']).dt.date
        q=h[(h['_d']==d)&(h['state'].astype(str).str.upper()==str(state).upper())]
        if not q.empty:
            if 'holiday_location_key' not in q.columns:return 'PUBLIC_HOLIDAY'
            def applies(v):
                if pd.isna(v) or str(v).strip()=='':return True
                return location_key is not None and str(v)==str(location_key)
            if q['holiday_location_key'].apply(applies).any():return 'PUBLIC_HOLIDAY'
    return 'SATURDAY' if d.weekday()==5 else 'SUNDAY' if d.weekday()==6 else 'WEEKDAY'


def _shift_type(start, end):
    start,end = parse_datetime_value(start),parse_datetime_value(end)
    if start.weekday() > 4: return 'NONE'
    if start.time() < time(6): return 'NIGHT'
    if end.date() > start.date(): return 'NIGHT'
    if end.time() > time(20): return 'AFTERNOON'
    return 'NONE'


def _ordinary_multiplier(c, emp_type, day_type, shift_type):
    m = float(c['ordinary_penalties'][emp_type][day_type])
    if day_type == 'WEEKDAY' and shift_type in ('AFTERNOON','NIGHT'):
        m = (1.25 if emp_type == 'CASUAL' else 1.0) + float(c['shiftwork'][shift_type]['loading'])
    return m


def _ot_multiplier(c, emp_type, work_group, day_type, ot_hours_before):
    if day_type == 'PUBLIC_HOLIDAY': base = 2.5
    elif day_type == 'SUNDAY': base = 2.0
    else:
        if emp_type == 'FULL_TIME':
            rule = c['overtime']['full_time'].get(work_group, c['overtime']['full_time']['OTHER'])
            first = float(rule['monday_to_saturday_first_band_hours'])
        else:
            first = float(c['overtime']['part_time_casual']['first_band_hours'])
        base = 1.5 if ot_hours_before < first else 2.0
    return base + (0.25 if emp_type == 'CASUAL' else 0.0)


def normalize_rosters(items):
    rows=[]
    for x in items or []:
        mins=0.0
        for b in x.get('breaks') or []:
            s=_dt(b.get('start_time') or b.get('startTime')); e=_dt(b.get('end_time') or b.get('endTime'))
            if s is not None and e is not None and e>s: mins += (e-s).total_seconds()/60
        rows.append({'rostered_shift_id':x.get('id'),'employee_id':x.get('member_id') or x.get('memberId'),'employee_name':x.get('member_full_name') or x.get('memberFullName'),'rostered_start_datetime':x.get('start_time') or x.get('startTime'),'rostered_end_datetime':x.get('end_time') or x.get('endTime'),'rostered_break_minutes':round(mins,2),'location_id':x.get('location_id') or x.get('locationId'),'work_site_id':x.get('work_site_id') or x.get('workSiteId'),'work_type_id':x.get('work_type_id') or x.get('workTypeId'),'work_type_name':x.get('work_type_name') or x.get('workTypeName'),'position_name':x.get('position_name') or x.get('positionName'),'roster_status':x.get('status'),'raw_json':json.dumps(x,default=str,separators=(',',':'))})
    return pd.DataFrame(rows)


def attach_rosters(timesheets, rosters):
    if timesheets is None or timesheets.empty:return timesheets
    out=timesheets.copy()
    for c in ('rostered_start_datetime','rostered_end_datetime','rostered_shift_match','rostered_shift_match_status'):
        if c not in out.columns:out[c]=None
    if rosters is None or rosters.empty:out['rostered_shift_match_status']='NO_ROSTER_DATA';return out
    rr=rosters.copy();rr['_s']=parse_datetime_series(rr['rostered_start_datetime']);rr['_e']=parse_datetime_series(rr['rostered_end_datetime'])
    for idx,r in out.iterrows():
        cand=rr[rr['employee_id'].astype(str)==str(r.get('employee_id'))];explicit=str(r.get('rostered_shift_id') or '')
        if explicit:
            hit=cand[cand['rostered_shift_id'].astype(str)==explicit]
            if len(hit)==1:
                row=hit.iloc[0];out.at[idx,'rostered_start_datetime']=row['rostered_start_datetime'];out.at[idx,'rostered_end_datetime']=row['rostered_end_datetime'];out.at[idx,'rostered_shift_match']=row['rostered_shift_id'];out.at[idx,'rostered_shift_match_status']='EXPLICIT_ID';continue
        ts_s=_dt(r.get('start_datetime'));ts_e=_dt(r.get('end_datetime'));overlaps=[]
        if ts_s is not None and ts_e is not None:
            for j,row in cand.iterrows():
                if pd.isna(row['_s']) or pd.isna(row['_e']):continue
                ov=max(0,(min(ts_e,row['_e'])-max(ts_s,row['_s'])).total_seconds())
                if ov>0:overlaps.append((ov,j))
        if not overlaps:out.at[idx,'rostered_shift_match_status']='NO_MATCH';continue
        overlaps.sort(reverse=True);best=overlaps[0]
        if len(overlaps)>1 and overlaps[1][0]==best[0]:out.at[idx,'rostered_shift_match_status']='AMBIGUOUS_OVERLAP';continue
        row=rr.loc[best[1]];out.at[idx,'rostered_start_datetime']=row['rostered_start_datetime'];out.at[idx,'rostered_end_datetime']=row['rostered_end_datetime'];out.at[idx,'rostered_shift_match']=row['rostered_shift_id'];out.at[idx,'rostered_shift_match_status']='BEST_OVERLAP'
    return out


def _flag(existing, flag):
    return '; '.join(sorted(set([x for x in str(existing or '').split('; ') if x]+[flag])))


def _mark_review(out, idx, flag):
    out.at[idx,'review_flags']=_flag(out.loc[idx].get('review_flags'),flag);out.at[idx,'entitlement_status']='REQUIRES_REVIEW'


def _conditions_complete(c):
    return bool(c and isinstance(c.get('ordinary_penalties'),dict) and isinstance(c.get('shiftwork'),dict) and isinstance(c.get('overtime'),dict))


def _reprice_interval(expected,evidence,base,c,emp_type,work_group,state,holidays,location_key,shift_start,shift_end,a,b,ot_before,component='OVERTIME_REPRICE'):
    stype=_shift_type(shift_start,shift_end);remaining=(b-a).total_seconds()/3600;cursor=a;cumulative=ot_before
    while remaining>1e-9:
        day=_day_type(cursor.date(),state,holidays,location_key);ord_mult=_ordinary_multiplier(c,emp_type,day,stype);midnight=cursor.normalize()+pd.Timedelta(days=1);day_room=(min(b,midnight)-cursor).total_seconds()/3600
        if day in ('SUNDAY','PUBLIC_HOLIDAY'):chunk=min(remaining,day_room)
        else:
            first=float(c['overtime']['full_time'].get(work_group,c['overtime']['full_time']['OTHER'])['monday_to_saturday_first_band_hours']) if emp_type=='FULL_TIME' else float(c['overtime']['part_time_casual']['first_band_hours']);room=max(0,first-cumulative);chunk=min(remaining,day_room,room) if room>1e-9 else min(remaining,day_room)
        if chunk<=1e-9:break
        ord_rate=effective_hourly_rate(base,ord_mult);expected-=line_amount(chunk,ord_rate);mult=_ot_multiplier(c,emp_type,work_group,day,cumulative);ot_rate=effective_hourly_rate(base,mult);amt=line_amount(chunk,ot_rate);expected+=amt;evidence.append({'component':component,'start':str(cursor),'hours':round(chunk,4),'day_type':day,'ordinary_rate_removed':float(ord_rate),'overtime_multiplier':mult,'overtime_rate':float(ot_rate),'amount_added':float(amt),'clause':'28'});cursor+=pd.Timedelta(hours=chunk);cumulative+=chunk;remaining-=chunk
    return expected,evidence,cumulative


def apply_rostered_and_daily_overtime(detail,timesheets,holidays,lib):
    if detail is None or detail.empty:return detail
    out=detail.copy();tsi={str(r['timesheet_id']):r.to_dict() for _,r in timesheets.iterrows()}
    for idx,r in out.iterrows():
        if pd.isna(r.get('base_hourly_rate')):continue
        ts=tsi.get(str(r.get('timesheet_id')),{});start=_dt(r.get('shift_start'));end=_dt(r.get('shift_end'))
        if start is None or end is None:continue
        c=lib.conditions(_dt(r.get('award_reference_date')) or start);emp_type=str(r.get('employment_type'));work_group=str(r.get('work_group') or 'OTHER');base=float(r.get('base_hourly_rate'));expected=Decimal(str(r.get('expected_amount') or 0));evidence=json.loads(r.get('calculation_evidence') or '[]');intervals=[]
        if emp_type not in ('FULL_TIME','PART_TIME','CASUAL'):
            _mark_review(out,idx,'OVERTIME_EMPLOYMENT_TYPE_MISSING');continue
        if not _conditions_complete(c):
            _mark_review(out,idx,'OVERTIME_CONDITION_PACK_MISSING');continue
        if emp_type=='FULL_TIME':
            rs=_dt(ts.get('rostered_start_datetime'));re=_dt(ts.get('rostered_end_datetime'));match=ts.get('rostered_shift_match_status')
            if rs is not None and re is not None and match in ('EXPLICIT_ID','BEST_OVERLAP'):
                if start<rs:intervals.append((start,min(end,rs)))
                if end>re:intervals.append((max(start,re),end))
            else:_mark_review(out,idx,'FT_ROSTER_REQUIRED_FOR_OVERTIME')
        else:
            threshold=float(c['overtime']['part_time_casual']['daily_trigger_hours'])
            sleepover=c.get('sleepover') or {}
            if _bool(ts.get('is_sleepover')) and sleepover.get('written_agreement_can_extend_ordinary_hours_to') and _bool(ts.get('sleepover_12h_written_agreement')):threshold=float(sleepover['written_agreement_can_extend_ordinary_hours_to'])
            excess=max(0,float(r.get('worked_hours') or 0)-threshold)
            if excess>0:
                if float(ts.get('unpaid_break_minutes') or 0)>0 or float(ts.get('break_units') or 0)>0:_mark_review(out,idx,'DAILY_OVERTIME_WITH_BREAK_ALLOCATION_REVIEW')
                else:intervals.append((end-pd.Timedelta(hours=excess),end))
        cumulative=0.0
        for a,b in intervals:expected,evidence,cumulative=_reprice_interval(expected,evidence,base,c,emp_type,work_group,r.get('state'),holidays,r.get('holiday_location_key'),start,end,a,b,cumulative)
        if intervals:out.at[idx,'expected_amount']=float(money(expected));out.at[idx,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
        if str(out.at[idx,'review_flags'] or '').strip():out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
    return out


def allocate_period_overtime(detail,holidays,lib):
    """Automatically allocate PT/casual 38h-week / 76h-fortnight overtime when unique."""
    if detail is None or detail.empty:return detail
    out=detail.copy();out['shift_start']=parse_datetime_series(out['shift_start']);out['shift_end']=parse_datetime_series(out['shift_end']);out['_week']=out['shift_start'].dt.to_period('W-SUN').astype(str)
    candidate_hours={}
    for (eid,w),g in out[out['employment_type'].isin(['PART_TIME','CASUAL'])].groupby(['employee_id','_week']):
        g=g.sort_values('shift_start');cum=0.0
        for idx,r in g.iterrows():
            h=float(r.get('worked_hours') or 0);before=cum;cum+=h;ex=max(0,cum-38)-max(0,before-38)
            if ex>1e-9:candidate_hours.setdefault(idx,[]).append(('WEEKLY',ex))
    p=out[out['employment_type'].isin(['PART_TIME','CASUAL'])].copy()
    for keys,g in p.groupby(['employee_id','pay_period_start','pay_period_end'],dropna=False):
        ps=_dt(keys[1]);pe=_dt(keys[2])
        if ps is None or pe is None or not (13<=(pe.normalize()-ps.normalize()).days<=14):continue
        g=g.sort_values('shift_start');cum=0.0
        for idx,r in g.iterrows():
            h=float(r.get('worked_hours') or 0);before=cum;cum+=h;ex=max(0,cum-76)-max(0,before-76)
            if ex>1e-9:candidate_hours.setdefault(idx,[]).append(('FORTNIGHT',ex))
    for idx,cands in candidate_hours.items():
        r=out.loc[idx];amounts={round(x[1],6) for x in cands}
        if len(amounts)>1:_mark_review(out,idx,'WEEKLY_FORTNIGHTLY_OVERTIME_ALLOCATION_CONFLICT');continue
        evidence=json.loads(r.get('calculation_evidence') or '[]')
        if any(e.get('component')=='OVERTIME_REPRICE' for e in evidence if isinstance(e,dict)):_mark_review(out,idx,'PERIOD_OVERTIME_OVERLAPS_DAILY_OR_ROSTER_OVERTIME');continue
        excess=max(amounts);start=_dt(r.get('shift_start'));end=_dt(r.get('shift_end'))
        if start is None or end is None or start.date()!=end.date() or excess>float(r.get('worked_hours') or 0):_mark_review(out,idx,'PERIOD_OVERTIME_ALLOCATION_REVIEW');continue
        base=float(r.get('base_hourly_rate') or 0);c=lib.conditions(_dt(r.get('award_reference_date')) or start)
        if base<=0:_mark_review(out,idx,'PERIOD_OVERTIME_BASE_RATE_MISSING');continue
        if not _conditions_complete(c):_mark_review(out,idx,'PERIOD_OVERTIME_CONDITION_PACK_MISSING');continue
        expected=Decimal(str(r.get('expected_amount') or 0));a=end-pd.Timedelta(hours=excess);expected,evidence,_=_reprice_interval(expected,evidence,base,c,r.get('employment_type'),r.get('work_group') or 'OTHER',r.get('state'),holidays,r.get('holiday_location_key'),start,end,a,end,0.0,component='PERIOD_OVERTIME_REPRICE');out.at[idx,'expected_amount']=float(money(expected));out.at[idx,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
    return out.drop(columns=['_week'])


def flag_period_overtime(detail):
    if detail is None or detail.empty:return detail
    out=detail.copy();out['shift_start']=parse_datetime_series(out['shift_start']);out['_week']=out['shift_start'].dt.to_period('W-SUN').astype(str);weekly=out.groupby(['employee_id','_week'],dropna=False)['worked_hours'].sum().to_dict();period=out.groupby(['employee_id','pay_period_start','pay_period_end'],dropna=False)['worked_hours'].sum().to_dict()
    for idx,r in out.iterrows():
        if r.get('employment_type') not in ('PART_TIME','CASUAL'):continue
        w=float(weekly.get((r['employee_id'],r['_week']),0))
        if w>38 and 'PERIOD_OVERTIME_REPRICE' not in str(r.get('calculation_evidence') or ''):out.at[idx,'review_flags']=_flag(r.get('review_flags'),f'WEEKLY_OVERTIME_THRESHOLD_EXCEEDED:{w:.2f}H')
        ps=_dt(r.get('pay_period_start'));pe=_dt(r.get('pay_period_end'))
        if ps is not None and pe is not None and 13<=(pe.normalize()-ps.normalize()).days<=14:
            total=float(period.get((r['employee_id'],r['pay_period_start'],r['pay_period_end']),0))
            if total>76 and 'PERIOD_OVERTIME_REPRICE' not in str(r.get('calculation_evidence') or ''):out.at[idx,'review_flags']=_flag(out.at[idx,'review_flags'],f'FORTNIGHT_OVERTIME_THRESHOLD_EXCEEDED:{total:.2f}H')
        if str(out.at[idx,'review_flags'] or '').strip():out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
    return out.drop(columns=['_week'])