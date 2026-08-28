from __future__ import annotations
import json
from datetime import time
from decimal import Decimal
import pandas as pd

from .money import money, effective_hourly_rate, line_amount


def _dt(v):
    if v is None or v == '': return None
    x = pd.to_datetime(v, errors='coerce')
    return None if pd.isna(x) else x


def _bool(v):
    if isinstance(v, bool): return v
    return str(v).strip().lower() in {'1','true','yes','y'}


def _day_type(d, state, holidays):
    if holidays is not None and not holidays.empty:
        h = holidays.copy(); h['_d'] = pd.to_datetime(h['holiday_date'], errors='coerce').dt.date
        if ((h['_d'] == d) & (h['state'].astype(str).str.upper() == str(state).upper())).any(): return 'PUBLIC_HOLIDAY'
    return 'SATURDAY' if d.weekday() == 5 else 'SUNDAY' if d.weekday() == 6 else 'WEEKDAY'


def _shift_type(start, end):
    start,end = pd.to_datetime(start),pd.to_datetime(end)
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
        rows.append({
            'rostered_shift_id':x.get('id'), 'employee_id':x.get('member_id') or x.get('memberId'),
            'employee_name':x.get('member_full_name') or x.get('memberFullName'),
            'rostered_start_datetime':x.get('start_time') or x.get('startTime'),
            'rostered_end_datetime':x.get('end_time') or x.get('endTime'),
            'rostered_break_minutes':round(mins,2), 'location_id':x.get('location_id') or x.get('locationId'),
            'work_site_id':x.get('work_site_id') or x.get('workSiteId'),
            'work_type_id':x.get('work_type_id') or x.get('workTypeId'),
            'work_type_name':x.get('work_type_name') or x.get('workTypeName'),
            'position_name':x.get('position_name') or x.get('positionName'), 'roster_status':x.get('status'),
            'raw_json':json.dumps(x,default=str,separators=(',',':'))})
    return pd.DataFrame(rows)


def attach_rosters(timesheets, rosters):
    if timesheets is None or timesheets.empty: return timesheets
    out=timesheets.copy()
    for c in ('rostered_start_datetime','rostered_end_datetime','rostered_shift_match','rostered_shift_match_status'):
        if c not in out.columns: out[c]=None
    if rosters is None or rosters.empty:
        out['rostered_shift_match_status']='NO_ROSTER_DATA'; return out
    rr=rosters.copy(); rr['_s']=pd.to_datetime(rr['rostered_start_datetime'],errors='coerce'); rr['_e']=pd.to_datetime(rr['rostered_end_datetime'],errors='coerce')
    for idx,r in out.iterrows():
        cand=rr[rr['employee_id'].astype(str)==str(r.get('employee_id'))]; explicit=str(r.get('rostered_shift_id') or '')
        if explicit:
            hit=cand[cand['rostered_shift_id'].astype(str)==explicit]
            if len(hit)==1:
                row=hit.iloc[0]; out.at[idx,'rostered_start_datetime']=row['rostered_start_datetime']; out.at[idx,'rostered_end_datetime']=row['rostered_end_datetime']; out.at[idx,'rostered_shift_match']=row['rostered_shift_id']; out.at[idx,'rostered_shift_match_status']='EXPLICIT_ID'; continue
        ts_s=_dt(r.get('start_datetime')); ts_e=_dt(r.get('end_datetime'))
        overlaps=[]
        if ts_s is not None and ts_e is not None:
            for j,row in cand.iterrows():
                if pd.isna(row['_s']) or pd.isna(row['_e']): continue
                ov=max(0,(min(ts_e,row['_e'])-max(ts_s,row['_s'])).total_seconds())
                if ov>0: overlaps.append((ov,j))
        if not overlaps: out.at[idx,'rostered_shift_match_status']='NO_MATCH'; continue
        overlaps.sort(reverse=True); best=overlaps[0]
        if len(overlaps)>1 and overlaps[1][0]==best[0]: out.at[idx,'rostered_shift_match_status']='AMBIGUOUS_OVERLAP'; continue
        row=rr.loc[best[1]]; out.at[idx,'rostered_start_datetime']=row['rostered_start_datetime']; out.at[idx,'rostered_end_datetime']=row['rostered_end_datetime']; out.at[idx,'rostered_shift_match']=row['rostered_shift_id']; out.at[idx,'rostered_shift_match_status']='BEST_OVERLAP'
    return out


def _flag(existing, flag):
    return '; '.join(sorted(set([x for x in str(existing or '').split('; ') if x]+[flag])))


def _reprice_interval(expected, evidence, base, c, emp_type, work_group, state, holidays, shift_start, shift_end, a, b, ot_before):
    stype=_shift_type(shift_start,shift_end); remaining=(b-a).total_seconds()/3600; cursor=a; cumulative=ot_before
    while remaining > 1e-9:
        day=_day_type(cursor.date(),state,holidays); ord_mult=_ordinary_multiplier(c,emp_type,day,stype)
        if day in ('SUNDAY','PUBLIC_HOLIDAY'): chunk=remaining
        else:
            first=float(c['overtime']['full_time'].get(work_group,c['overtime']['full_time']['OTHER'])['monday_to_saturday_first_band_hours']) if emp_type=='FULL_TIME' else float(c['overtime']['part_time_casual']['first_band_hours'])
            room=max(0,first-cumulative); chunk=min(remaining,room) if room>1e-9 else remaining
        ord_rate=effective_hourly_rate(base,ord_mult); expected -= line_amount(chunk,ord_rate)
        mult=_ot_multiplier(c,emp_type,work_group,day,cumulative); ot_rate=effective_hourly_rate(base,mult); amt=line_amount(chunk,ot_rate); expected += amt
        evidence.append({'component':'OVERTIME_REPRICE','start':str(cursor),'hours':round(chunk,4),'day_type':day,'ordinary_rate_removed':float(ord_rate),'overtime_multiplier':mult,'overtime_rate':float(ot_rate),'amount_added':float(amt),'clause':'28'})
        cursor += pd.Timedelta(hours=chunk); cumulative += chunk; remaining -= chunk
    return expected,evidence,cumulative


def apply_rostered_and_daily_overtime(detail, timesheets, holidays, lib):
    if detail is None or detail.empty: return detail
    out=detail.copy(); tsi={str(r['timesheet_id']):r.to_dict() for _,r in timesheets.iterrows()}
    for idx,r in out.iterrows():
        if pd.isna(r.get('base_hourly_rate')): continue
        ts=tsi.get(str(r.get('timesheet_id')),{}); start=_dt(r.get('shift_start')); end=_dt(r.get('shift_end'))
        if start is None or end is None: continue
        c=lib.conditions(_dt(r.get('award_reference_date')) or start); emp_type=str(r.get('employment_type')); work_group=str(r.get('work_group') or 'OTHER'); base=float(r.get('base_hourly_rate'))
        expected=Decimal(str(r.get('expected_amount') or 0)); evidence=json.loads(r.get('calculation_evidence') or '[]'); intervals=[]
        if emp_type=='FULL_TIME':
            rs=_dt(ts.get('rostered_start_datetime')); re=_dt(ts.get('rostered_end_datetime')); match=ts.get('rostered_shift_match_status')
            if rs is not None and re is not None and match in ('EXPLICIT_ID','BEST_OVERLAP'):
                if start<rs: intervals.append((start,min(end,rs)))
                if end>re: intervals.append((max(start,re),end))
            else: out.at[idx,'review_flags']=_flag(r.get('review_flags'),'FT_ROSTER_REQUIRED_FOR_OVERTIME')
        elif emp_type in ('PART_TIME','CASUAL'):
            threshold=float(c['overtime']['part_time_casual']['daily_trigger_hours'])
            if _bool(ts.get('is_sleepover')) and c['sleepover'].get('written_agreement_can_extend_ordinary_hours_to') and _bool(ts.get('sleepover_12h_written_agreement')): threshold=float(c['sleepover']['written_agreement_can_extend_ordinary_hours_to'])
            excess=max(0,float(r.get('worked_hours') or 0)-threshold)
            if excess>0:
                if float(ts.get('unpaid_break_minutes') or 0)>0 or float(ts.get('break_units') or 0)>0: out.at[idx,'review_flags']=_flag(r.get('review_flags'),'DAILY_OVERTIME_WITH_BREAK_ALLOCATION_REVIEW')
                else: intervals.append((end-pd.Timedelta(hours=excess),end))
        cumulative=0.0
        for a,b in intervals: expected,evidence,cumulative=_reprice_interval(expected,evidence,base,c,emp_type,work_group,r.get('state'),holidays,start,end,a,b,cumulative)
        if intervals: out.at[idx,'expected_amount']=float(money(expected)); out.at[idx,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
        if str(out.at[idx,'review_flags'] or '').strip(): out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
    return out


def flag_period_overtime(detail):
    if detail is None or detail.empty: return detail
    out=detail.copy(); out['shift_start']=pd.to_datetime(out['shift_start'],errors='coerce'); out['_week']=out['shift_start'].dt.to_period('W-SUN').astype(str)
    weekly=out.groupby(['employee_id','_week'],dropna=False)['worked_hours'].sum().to_dict(); period=out.groupby(['employee_id','pay_period_start','pay_period_end'],dropna=False)['worked_hours'].sum().to_dict()
    for idx,r in out.iterrows():
        if r.get('employment_type') not in ('PART_TIME','CASUAL'): continue
        w=float(weekly.get((r['employee_id'],r['_week']),0))
        if w>38: out.at[idx,'review_flags']=_flag(r.get('review_flags'),f'WEEKLY_OVERTIME_THRESHOLD_EXCEEDED:{w:.2f}H')
        ps=_dt(r.get('pay_period_start')); pe=_dt(r.get('pay_period_end'))
        if ps is not None and pe is not None and 13 <= (pe.normalize()-ps.normalize()).days <= 14:
            total=float(period.get((r['employee_id'],r['pay_period_start'],r['pay_period_end']),0))
            if total>76: out.at[idx,'review_flags']=_flag(out.at[idx,'review_flags'],f'FORTNIGHT_OVERTIME_THRESHOLD_EXCEEDED:{total:.2f}H')
        if str(out.at[idx,'review_flags'] or '').strip(): out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
    return out.drop(columns=['_week'])
