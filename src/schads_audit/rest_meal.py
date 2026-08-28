from __future__ import annotations
import json
from decimal import Decimal
import pandas as pd

from .money import money,effective_hourly_rate,line_amount
from .roster_overtime import _day_type,_ot_multiplier


def _dt(v):
    x=pd.to_datetime(v,errors='coerce')
    return None if pd.isna(x) else x


def _flag(existing,flag):
    parts=[x for x in str(existing or '').split('; ') if x];parts.append(flag)
    return '; '.join(sorted(set(parts)))


def _has_overtime(evidence_json):
    try:items=json.loads(evidence_json or '[]')
    except Exception:return False
    return any('OVERTIME' in str(x.get('component','')).upper() for x in items)


def _matching_control(register,eid,timesheet_id,start):
    if register is None or register.empty:return None
    q=register[register['employee_id'].astype(str)==str(eid)].copy()
    if q.empty:return None
    if 'timesheet_id' in q.columns and timesheet_id not in (None,''):
        hit=q[q['timesheet_id'].astype(str)==str(timesheet_id)]
        if not hit.empty:return hit.iloc[0].to_dict()
    if 'shift_start' in q.columns and start is not None:
        q['_s']=pd.to_datetime(q['shift_start'],errors='coerce')
        hit=q[q['_s']==start]
        if not hit.empty:return hit.iloc[0].to_dict()
    return None


def apply_rest_after_overtime(detail,rest_controls=None):
    """Apply clause 28.3 evidence checks and, where controlled facts exist,
    ensure resumed work is paid at least double time until release.

    Casuals are excluded by clause 28.3. Remote-work events are outside this
    shift-detail function and do not count for this rest-period rule.
    """
    if detail is None or detail.empty:return detail
    out=detail.copy();out['_s']=pd.to_datetime(out['shift_start'],errors='coerce');out['_e']=pd.to_datetime(out['shift_end'],errors='coerce')
    for eid,g in out.dropna(subset=['_s','_e']).groupby(out['employee_id'].astype(str)):
        idxs=g.sort_values('_s').index.tolist()
        for prev_i,next_i in zip(idxs[:-1],idxs[1:]):
            prev=out.loc[prev_i];nxt=out.loc[next_i]
            if str(nxt.get('employment_type'))=='CASUAL' or not _has_overtime(prev.get('calculation_evidence')):continue
            gap=(nxt['_s']-prev['_e']).total_seconds()/3600
            if gap>=10:continue
            deficit=10-gap
            out.at[next_i,'review_flags']=_flag(nxt.get('review_flags'),f'REST_AFTER_OVERTIME_UNDER_10H:{gap:.2f}H')
            control=_matching_control(rest_controls,eid,nxt.get('timesheet_id'),nxt['_s'])
            instructed=str((control or {}).get('employer_instructed_resume','')).strip().lower() in {'1','true','yes','y'}
            if not instructed:
                out.at[next_i,'review_flags']=_flag(out.at[next_i,'review_flags'],'REST_AFTER_OVERTIME_EMPLOYER_INSTRUCTION_VERIFY')
                out.at[next_i,'entitlement_status']='REQUIRES_REVIEW';continue
            base=float(nxt.get('base_hourly_rate') or 0)
            if base<=0:
                out.at[next_i,'review_flags']=_flag(out.at[next_i,'review_flags'],'REST_AFTER_OVERTIME_RATE_MISSING');out.at[next_i,'entitlement_status']='REQUIRES_REVIEW';continue
            double=effective_hourly_rate(base,2.0)
            try:evidence=json.loads(nxt.get('calculation_evidence') or '[]')
            except Exception:evidence=[]
            delta=Decimal('0');covered=0.0
            for item in evidence:
                hours=float(item.get('hours') or 0);current=item.get('effective_hourly_rate') or item.get('rate')
                if hours<=0 or current is None:continue
                covered+=hours;cur=Decimal(str(current));d=max(Decimal('0'),Decimal(str(double))-cur);delta+=Decimal(str(hours))*d
            if covered<=0:
                out.at[next_i,'review_flags']=_flag(out.at[next_i,'review_flags'],'REST_AFTER_OVERTIME_REPRICE_EVIDENCE_MISSING');out.at[next_i,'entitlement_status']='REQUIRES_REVIEW';continue
            top=money(delta)
            if top>0:
                out.at[next_i,'expected_amount']=float(money(Decimal(str(nxt.get('expected_amount') or 0))+top))
                evidence.append({'component':'REST_AFTER_OVERTIME_DOUBLE_TIME_TOPUP','prior_timesheet_id':prev.get('timesheet_id'),'rest_hours':round(gap,4),'rest_deficit_hours':round(deficit,4),'minimum_rate':float(double),'amount':float(top),'clause':'28.3(b)'})
                out.at[next_i,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
            # The calculation can be monetary, but the breach still remains a compliance finding.
            out.at[next_i,'entitlement_status']='REQUIRES_REVIEW'
    return out.drop(columns=['_s','_e'])


def apply_meal_break_events(detail,timesheets,meal_events,holidays,lib):
    """Apply controlled meal-break evidence under clause 27.1.

    WORKED_THROUGH requires the scheduled meal time and actual break time (or
    shift end). CLIENT_MEAL can restore a break that payroll/timesheet data
    deducted even though the client meal counts as work.
    """
    if detail is None or detail.empty or meal_events is None or meal_events.empty:return detail
    out=detail.copy();tsi={str(r['timesheet_id']):r.to_dict() for _,r in timesheets.iterrows()}
    for _,ev in meal_events.iterrows():
        tid=str(ev.get('timesheet_id') or '');hits=out[out['timesheet_id'].astype(str)==tid]
        if hits.empty:continue
        i=hits.index[0];r=out.loc[i];ts=tsi.get(tid,{})
        mode=str(ev.get('mode') or '').upper();base=float(r.get('base_hourly_rate') or 0);start=_dt(r.get('shift_start'));end=_dt(r.get('shift_end'))
        if base<=0 or start is None or end is None:
            out.at[i,'review_flags']=_flag(r.get('review_flags'),'MEAL_EVENT_RATE_OR_SHIFT_MISSING');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
        try:evidence=json.loads(r.get('calculation_evidence') or '[]')
        except Exception:evidence=[]
        if mode=='CLIENT_MEAL':
            mins=float(ev.get('paid_meal_minutes') or ev.get('deducted_break_minutes') or 0)
            if mins<=0:
                out.at[i,'review_flags']=_flag(r.get('review_flags'),'CLIENT_MEAL_DURATION_MISSING');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
            ordinary_rate=None
            for x in evidence:
                if x.get('component')=='ORDINARY_OR_PENALTY' and x.get('effective_hourly_rate') is not None:
                    ordinary_rate=float(x['effective_hourly_rate']);break
            ordinary_rate=ordinary_rate or float(effective_hourly_rate(base,1.25 if r.get('employment_type')=='CASUAL' else 1.0))
            amt=line_amount(mins/60,ordinary_rate);out.at[i,'expected_amount']=float(money(Decimal(str(r.get('expected_amount') or 0))+amt));evidence.append({'component':'CLIENT_MEAL_PAID_TIME','minutes':mins,'rate':ordinary_rate,'amount':float(amt),'clause':'27.1(c)'})
            flags=[x for x in str(out.at[i,'review_flags'] or '').split('; ') if x and x!='MEAL_BREAK_REVIEW'];out.at[i,'review_flags']='; '.join(flags);out.at[i,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
        elif mode=='WORKED_THROUGH':
            scheduled=_dt(ev.get('scheduled_break_start'));actual=_dt(ev.get('actual_break_start')) or end
            if scheduled is None or actual<=scheduled:
                out.at[i,'review_flags']=_flag(r.get('review_flags'),'WORKED_THROUGH_MEAL_TIMES_INVALID');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
            if scheduled.date()!=actual.date():
                out.at[i,'review_flags']=_flag(r.get('review_flags'),'WORKED_THROUGH_MEAL_CROSS_MIDNIGHT_REVIEW');out.at[i,'entitlement_status']='REQUIRES_REVIEW';continue
            affected=(actual-scheduled).total_seconds()/3600;deducted=float(ev.get('deducted_break_minutes') or 0)/60
            cond=lib.conditions(r.get('award_reference_date') or start);day=_day_type(scheduled.date(),r.get('state'),holidays,r.get('holiday_location_key'));mult=_ot_multiplier(cond,r.get('employment_type'),r.get('work_group') or 'OTHER',day,0);ot_rate=effective_hourly_rate(base,mult)
            ordinary_rate=None
            for x in evidence:
                if x.get('component')=='ORDINARY_OR_PENALTY' and str(x.get('date'))==str(scheduled.date()):ordinary_rate=x.get('effective_hourly_rate');break
            ordinary_rate=float(ordinary_rate or effective_hourly_rate(base,1.25 if r.get('employment_type')=='CASUAL' else 1.0))
            already_paid=max(0,affected-deducted);delta=line_amount(deducted,ot_rate)+money(Decimal(str(already_paid))*(Decimal(str(ot_rate))-Decimal(str(ordinary_rate))))
            out.at[i,'expected_amount']=float(money(Decimal(str(r.get('expected_amount') or 0))+delta));evidence.append({'component':'WORKED_THROUGH_MEAL_OVERTIME','affected_hours':round(affected,4),'deducted_hours_restored':round(deducted,4),'overtime_rate':float(ot_rate),'ordinary_rate_replaced':ordinary_rate,'amount':float(money(delta)),'clause':'27.1(b)'})
            flags=[x for x in str(out.at[i,'review_flags'] or '').split('; ') if x and x!='MEAL_BREAK_REVIEW'];out.at[i,'review_flags']='; '.join(flags);out.at[i,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
        else:
            out.at[i,'review_flags']=_flag(r.get('review_flags'),f'UNKNOWN_MEAL_EVENT_MODE:{mode}');out.at[i,'entitlement_status']='REQUIRES_REVIEW'
    return out
