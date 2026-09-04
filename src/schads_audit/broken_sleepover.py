from __future__ import annotations
import json
from decimal import Decimal
import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value
from .money import money, effective_hourly_rate, line_amount


def _dt(v):
    if v in (None, ''): return None
    x = parse_datetime_value(v)
    return None if pd.isna(x) else x


def _flag(existing, flag):
    parts=[x for x in str(existing or '').split('; ') if x];parts.append(flag);return '; '.join(sorted(set(parts)))


def _bool(v):
    if isinstance(v,bool): return v
    return str(v).strip().lower() in {'1','true','yes','y'}


def _overlap_hours(a1,a2,b1,b2):
    s=max(a1,b1);e=min(a2,b2);return max(0.0,(e-s).total_seconds()/3600) if e>s else 0.0


def _mark_review(out, indices, flag):
    for i in indices:
        out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),flag)
        out.at[i,'entitlement_status']='REQUIRES_REVIEW'


def _single_period_rate(detail_row):
    try:ev=json.loads(detail_row.get('calculation_evidence') or '[]')
    except Exception:return None
    rates=[]
    for x in ev:
        if isinstance(x,dict) and x.get('component')=='ORDINARY_OR_PENALTY' and x.get('effective_hourly_rate') is not None:rates.append(round(float(x['effective_hourly_rate']),6))
    unique=sorted(set(rates));return unique[0] if len(unique)==1 else None


def group_broken_shifts(timesheets,gap_minutes=30):
    if timesheets is None or timesheets.empty:return timesheets
    out=timesheets.copy()
    for c in ('broken_shift_group_id','broken_shift_period_number','broken_shift_period_count','broken_shift_breaks','broken_shift_group_status'):
        if c not in out.columns:out[c]=None
    if 'work_group' not in out.columns:return out
    out['_s']=parse_datetime_series(out['start_datetime']);out['_e']=parse_datetime_series(out['end_datetime']);eligible=out['work_group'].astype(str).isin(['DISABILITY_SERVICES','HOME_CARE'])
    for (eid,day),g in out[eligible].dropna(subset=['_s','_e']).groupby([out.loc[eligible,'employee_id'].astype(str),out.loc[eligible,'_s'].dt.date]):
        g=g.sort_values('_s');periods=[];current=[]
        for idx,r in g.iterrows():
            if not current:current=[idx];continue
            prev=out.loc[current[-1]];gap=(r['_s']-prev['_e']).total_seconds()/60
            if gap>=gap_minutes:current.append(idx)
            else:
                if len(current)>1:periods.append(current)
                current=[idx]
        if len(current)>1:periods.append(current)
        for seq in periods:
            first=out.loc[seq[0],'_s'];last=out.loc[seq[-1],'_e'];span=(last-first).total_seconds()/3600;status='TOO_MANY_WORK_PERIODS' if len(seq)>3 else 'INVALID_SPAN' if span>24 else 'INFERRED';gid=f'BS:{eid}:{day}:{first.strftime("%H%M")}'
            for n,idx in enumerate(seq,1):out.at[idx,'broken_shift_group_id']=gid;out.at[idx,'broken_shift_period_number']=n;out.at[idx,'broken_shift_period_count']=len(seq);out.at[idx,'broken_shift_breaks']=len(seq)-1;out.at[idx,'broken_shift_group_status']=status
    return out.drop(columns=['_s','_e'])


def apply_broken_shift_rules(detail,timesheets,lib):
    if detail is None or detail.empty:return detail
    out=detail.copy();tsi={str(r['timesheet_id']):r.to_dict() for _,r in timesheets.iterrows()};groups={}
    for _,r in timesheets.iterrows():
        gid=r.get('broken_shift_group_id')
        if gid:groups.setdefault(str(gid),[]).append(r.to_dict())
    processed=set()
    for _,r in out.iterrows():
        ts=tsi.get(str(r.get('timesheet_id')),{});gid=ts.get('broken_shift_group_id')
        if not gid or str(gid) in processed:continue
        gid=str(gid);processed.add(gid);members=groups.get(gid,[]);member_ids={str(x.get('timesheet_id')) for x in members};di=out[out['timesheet_id'].astype(str).isin(member_ids)].index.tolist()
        if len(di)<2:continue
        work_group=str(out.loc[di[0]].get('work_group') or '')
        if work_group not in ('DISABILITY_SERVICES','HOME_CARE'):_mark_review(out,di,'BROKEN_SHIFT_INELIGIBLE_WORK_GROUP');continue
        starts=[_dt(x.get('start_datetime')) for x in members];ends=[_dt(x.get('end_datetime')) for x in members];starts=[x for x in starts if x is not None];ends=[x for x in ends if x is not None]
        if not starts or not ends:_mark_review(out,di,'BROKEN_SHIFT_INTERVAL_EVIDENCE_MISSING');continue
        first=min(starts);last=max(ends);span=(last-first).total_seconds()/3600;ref=_dt(out.loc[di[0]].get('award_reference_date')) or first;c=lib.conditions(ref);breaks=len(members)-1
        if not c or not isinstance(c.get('broken_shift'),dict):_mark_review(out,di,'BROKEN_SHIFT_CONDITION_PACK_MISSING');continue
        if breaks>int(c['broken_shift']['max_unpaid_breaks']):_mark_review(out,di,'BROKEN_SHIFT_MORE_THAN_TWO_BREAKS');continue
        if breaks==2:_mark_review(out,di,'TWO_BREAK_BROKEN_SHIFT_AGREEMENT_VERIFY')
        key='broken_shift_1_break' if breaks==1 else 'broken_shift_2_breaks';allowance,ap=lib.allowance(key,ref)
        if allowance:
            first_idx=min(di,key=lambda i:_dt(out.loc[i,'shift_start']) or pd.Timestamp.max);ev=json.loads(out.loc[first_idx].get('calculation_evidence') or '[]');amt=money(allowance['amount']);out.at[first_idx,'expected_amount']=float(money(Decimal(str(out.loc[first_idx,'expected_amount'] or 0))+amt));ev.append({'component':'BROKEN_SHIFT_ALLOWANCE','group_id':gid,'breaks':breaks,'amount':float(amt),'allowance_pack_id':ap['allowance_pack_id'],'clause':'25.6'});out.at[first_idx,'calculation_evidence']=json.dumps(ev,default=str,separators=(',',':'))
        else:_mark_review(out,di,'BROKEN_SHIFT_ALLOWANCE_MISSING')
        for i in di:
            if out.loc[i].get('employment_type') in ('PART_TIME','CASUAL') and float(out.loc[i].get('worked_hours') or 0)<2:
                rate=_single_period_rate(out.loc[i])
                if rate is None:out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),'BROKEN_SHIFT_MINIMUM_MULTIRATE_REVIEW');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
                short=2-float(out.loc[i].get('worked_hours') or 0);top=line_amount(short,rate);out.at[i,'expected_amount']=float(money(Decimal(str(out.loc[i,'expected_amount'] or 0))+top));ev=json.loads(out.loc[i].get('calculation_evidence') or '[]');ev.append({'component':'BROKEN_SHIFT_MINIMUM_PERIOD_TOPUP','group_id':gid,'hours':short,'rate':float(rate),'amount':float(top),'clause':'10.5 / 25.6'});out.at[i,'calculation_evidence']=json.dumps(ev,default=str,separators=(',',':'))
        if span>float(c['broken_shift']['max_span_hours']):
            boundary=first+pd.Timedelta(hours=float(c['broken_shift']['max_span_hours']))
            for i in di:
                s=_dt(out.loc[i,'shift_start']);e=_dt(out.loc[i,'shift_end']);excess=_overlap_hours(s,e,boundary,last) if s and e else 0
                if excess<=0:continue
                if 'OVERTIME_REPRICE' in str(out.loc[i].get('calculation_evidence') or ''):out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),'BROKEN_SHIFT_12H_OVERTIME_INTERACTION_REVIEW');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
                current=_single_period_rate(out.loc[i])
                if current is None:out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),'BROKEN_SHIFT_12H_MULTIRATE_REVIEW');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
                base=float(out.loc[i].get('base_hourly_rate') or 0);emp=out.loc[i].get('employment_type')
                if base<=0 or emp not in ('FULL_TIME','PART_TIME','CASUAL'):out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),'BROKEN_SHIFT_12H_RATE_OR_EMPLOYMENT_TYPE_MISSING');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
                double=effective_hourly_rate(base,2.25 if emp=='CASUAL' else 2.0);delta=line_amount(excess,double)-line_amount(excess,current);out.at[i,'expected_amount']=float(money(Decimal(str(out.loc[i,'expected_amount'] or 0))+delta));ev=json.loads(out.loc[i].get('calculation_evidence') or '[]');ev.append({'component':'BROKEN_SHIFT_BEYOND_12H_REPRICE','group_id':gid,'hours':excess,'ordinary_rate_removed':float(current),'double_time_rate':float(double),'delta':float(delta),'clause':'25.6'});out.at[i,'calculation_evidence']=json.dumps(ev,default=str,separators=(',',':'))
    return out


def group_sleepovers(timesheets):
    if timesheets is None or timesheets.empty:return timesheets
    out=timesheets.copy()
    for c in ('sleepover_group_id','sleepover_period_role'):
        if c not in out.columns:out[c]=None
    out['_s']=parse_datetime_series(out['start_datetime']);out['_e']=parse_datetime_series(out['end_datetime'])
    for idx,r in out.iterrows():
        if not _bool(r.get('is_sleepover')):continue
        s,e=r['_s'],r['_e']
        if pd.isna(s) or pd.isna(e):continue
        gid=f'SO:{r.get("employee_id")}:{s.isoformat()}';out.at[idx,'sleepover_group_id']=gid;out.at[idx,'sleepover_period_role']='SLEEPOVER';emp=out[out['employee_id'].astype(str)==str(r.get('employee_id'))];before=emp[(emp.index!=idx)&(emp['_e']<=s)&((s-emp['_e']).dt.total_seconds().abs()<=60)].sort_values('_e',ascending=False);after=emp[(emp.index!=idx)&(emp['_s']>=e)&((emp['_s']-e).dt.total_seconds().abs()<=60)].sort_values('_s')
        if not before.empty:j=before.index[0];out.at[j,'sleepover_group_id']=gid;out.at[j,'sleepover_period_role']='BEFORE'
        if not after.empty:j=after.index[0];out.at[j,'sleepover_group_id']=gid;out.at[j,'sleepover_period_role']='AFTER'
    return out.drop(columns=['_s','_e'])


def apply_sleepover_group_rules(detail,timesheets,lib):
    if detail is None or detail.empty:return detail
    out=detail.copy();tsi={str(r['timesheet_id']):r.to_dict() for _,r in timesheets.iterrows()};groups={}
    for _,t in timesheets.iterrows():
        gid=t.get('sleepover_group_id')
        if gid:groups.setdefault(str(gid),[]).append(t.to_dict())
    for gid,members in groups.items():
        roles={m.get('sleepover_period_role'):m for m in members};sleep=roles.get('SLEEPOVER')
        if not sleep:continue
        member_ids={str(m.get('timesheet_id')) for m in members};di=out[out['timesheet_id'].astype(str).isin(member_ids)].index.tolist()
        if not di:continue
        ref=_dt(out.loc[di[0]].get('award_reference_date')) or _dt(sleep.get('start_datetime'));c=lib.conditions(ref) if ref is not None else None
        if not c or not isinstance(c.get('sleepover'),dict):_mark_review(out,di,'SLEEPOVER_CONDITION_PACK_MISSING');continue
        continuous=bool(c['sleepover'].get('surrounding_work_is_one_shift'));before=roles.get('BEFORE');after=roles.get('AFTER')
        for role,item in [('BEFORE',before),('AFTER',after)]:
            if not item:continue
            hits=out[out['timesheet_id'].astype(str)==str(item.get('timesheet_id'))].index
            if len(hits)==0:continue
            i=hits[0];hrs=float(out.loc[i].get('worked_hours') or 0)
            if hrs<4:
                rate=_single_period_rate(out.loc[i])
                if rate is None:out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),'SLEEPOVER_MINIMUM_MULTIRATE_REVIEW');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
                short=4-hrs;top=line_amount(short,rate);out.at[i,'expected_amount']=float(money(Decimal(str(out.loc[i,'expected_amount'] or 0))+top));ev=json.loads(out.loc[i].get('calculation_evidence') or '[]');ev.append({'component':'SLEEPOVER_SURROUNDING_WORK_MINIMUM_TOPUP','role':role,'hours':short,'rate':float(rate),'amount':float(top),'clause':'25.7'});out.at[i,'calculation_evidence']=json.dumps(ev,default=str,separators=(',',':'))
        if continuous and before and after:
            active=sum(float(out.loc[i].get('worked_hours') or 0) for i in di if tsi.get(str(out.loc[i,'timesheet_id']),{}).get('sleepover_period_role') in ('BEFORE','AFTER'));agreed=_bool(sleep.get('sleepover_12h_written_agreement'));threshold=12.0 if agreed else 10.0
            if active>threshold:_mark_review(out,di,f'SLEEPOVER_CONTINUOUS_SHIFT_OVERTIME_EXCESS:{active-threshold:.2f}H')
            if agreed:
                for role,item in [('BEFORE',before),('AFTER',after)]:
                    if item:
                        hits=out[out['timesheet_id'].astype(str)==str(item.get('timesheet_id'))].index
                        if len(hits) and float(out.loc[hits[0]].get('worked_hours') or 0)>8:
                            i=hits[0];out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),f'SLEEPOVER_{role}_MORE_THAN_8H');out.at[i,'entitlement_status']='REQUIRES_REVIEW'
    return out
