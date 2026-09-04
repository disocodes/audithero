from __future__ import annotations
import json
from decimal import Decimal
import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value
from .money import money,effective_hourly_rate,line_amount
from .roster_overtime import _day_type,_ot_multiplier


def _dt(v):
    x=parse_datetime_value(v)
    return None if pd.isna(x) else x


def _flag(existing,flag):
    parts=[x for x in str(existing or '').split('; ') if x];parts.append(flag)
    return '; '.join(sorted(set(parts)))


def _review(out,i,flag):
    out.at[i,'review_flags']=_flag(out.loc[i].get('review_flags'),flag);out.at[i,'entitlement_status']='REQUIRES_REVIEW'


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
        q['_s']=parse_datetime_series(q['shift_start'])
        hit=q[q['_s']==start]
        if not hit.empty:return hit.iloc[0].to_dict()
    return None


def apply_rest_after_overtime(detail,rest_controls=None):
    """Apply clause 28.3 evidence checks and controlled double-time top-ups."""
    if detail is None or detail.empty:return detail
    out=detail.copy();out['_s']=parse_datetime_series(out['shift_start']);out['_e']=parse_datetime_series(out['shift_end'])
    for eid,g in out.dropna(subset=['_s','_e']).groupby(out['employee_id'].astype(str)):
        idxs=g.sort_values('_s').index.tolist()
        for prev_i,next_i in zip(idxs[:-1],idxs[1:]):
            prev=out.loc[prev_i];nxt=out.loc[next_i]
            if str(nxt.get('employment_type'))=='CASUAL' or not _has_overtime(prev.get('calculation_evidence')):continue
            gap=(nxt['_s']-prev['_e']).total_seconds()/3600
            if gap>=10:continue
            deficit=10-gap;out.at[next_i,'review_flags']=_flag(nxt.get('review_flags'),f'REST_AFTER_OVERTIME_UNDER_10H:{gap:.2f}H')
            control=_matching_control(rest_controls,eid,nxt.get('timesheet_id'),nxt['_s']);instructed=str((control or {}).get('employer_instructed_resume','')).strip().lower() in {'1','true','yes','y'}
            if not instructed:_review(out,next_i,'REST_AFTER_OVERTIME_EMPLOYER_INSTRUCTION_VERIFY');continue
            base=float(nxt.get('base_hourly_rate') or 0)
            if base<=0:_review(out,next_i,'REST_AFTER_OVERTIME_RATE_MISSING');continue
            double=effective_hourly_rate(base,2.0)
            try:evidence=json.loads(nxt.get('calculation_evidence') or '[]')
            except Exception:evidence=[]
            delta=Decimal('0');covered=0.0
            for item in evidence:
                if not isinstance(item,dict):continue
                hours=float(item.get('hours') or 0);current=item.get('effective_hourly_rate') or item.get('rate')
                if hours<=0 or current is None:continue
                covered+=hours;cur=Decimal(str(current));d=max(Decimal('0'),Decimal(str(double))-cur);delta+=Decimal(str(hours))*d
            if covered<=0:_review(out,next_i,'REST_AFTER_OVERTIME_REPRICE_EVIDENCE_MISSING');continue
            top=money(delta)
            if top>0:
                out.at[next_i,'expected_amount']=float(money(Decimal(str(nxt.get('expected_amount') or 0))+top));evidence.append({'component':'REST_AFTER_OVERTIME_DOUBLE_TIME_TOPUP','prior_timesheet_id':prev.get('timesheet_id'),'rest_hours':round(gap,4),'rest_deficit_hours':round(deficit,4),'minimum_rate':float(double),'amount':float(top),'clause':'28.3(b)'});out.at[next_i,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
            out.at[next_i,'entitlement_status']='REQUIRES_REVIEW'
    return out.drop(columns=['_s','_e'])


def apply_meal_break_events(detail,timesheets,meal_events,holidays,lib):
    """Apply controlled meal-break evidence under clause 27.1."""
    if detail is None or detail.empty or meal_events is None or meal_events.empty:return detail
    out=detail.copy();tsi={str(r['timesheet_id']):r.to_dict() for _,r in timesheets.iterrows()}
    for _,ev in meal_events.iterrows():
        tid=str(ev.get('timesheet_id') or '');hits=out[out['timesheet_id'].astype(str)==tid]
        if hits.empty:continue
        i=hits.index[0];r=out.loc[i];mode=str(ev.get('mode') or '').upper();base=float(r.get('base_hourly_rate') or 0);start=_dt(r.get('shift_start'));end=_dt(r.get('shift_end'));emp_type=str(r.get('employment_type') or '')
        if base<=0 or start is None or end is None:_review(out,i,'MEAL_EVENT_RATE_OR_SHIFT_MISSING');continue
        if emp_type not in ('FULL_TIME','PART_TIME','CASUAL'):_review(out,i,'MEAL_EVENT_EMPLOYMENT_TYPE_MISSING');continue
        try:evidence=json.loads(r.get('calculation_evidence') or '[]')
        except Exception:evidence=[]
        if mode=='CLIENT_MEAL':
            mins=pd.to_numeric(pd.Series([ev.get('paid_meal_minutes') if pd.notna(ev.get('paid_meal_minutes')) else ev.get('deducted_break_minutes')]),errors='coerce').iloc[0]
            if pd.isna(mins) or float(mins)<=0:_review(out,i,'CLIENT_MEAL_DURATION_MISSING');continue
            mins=float(mins);ordinary_rate=None
            for x in evidence:
                if isinstance(x,dict) and x.get('component')=='ORDINARY_OR_PENALTY' and x.get('effective_hourly_rate') is not None:ordinary_rate=float(x['effective_hourly_rate']);break
            if ordinary_rate is None:
                cond=lib.conditions(r.get('award_reference_date') or start)
                if not cond:_review(out,i,'CLIENT_MEAL_CONDITION_PACK_MISSING');continue
                day=_day_type(start.date(),r.get('state'),holidays,r.get('holiday_location_key'))
                try:
                    from .roster_overtime import _ordinary_multiplier, _shift_type
                    ordinary_rate=float(effective_hourly_rate(base,_ordinary_multiplier(cond,emp_type,day,_shift_type(start,end))))
                except Exception:_review(out,i,'CLIENT_MEAL_RATE_RECONSTRUCTION_REVIEW');continue
            amt=line_amount(mins/60,ordinary_rate);out.at[i,'expected_amount']=float(money(Decimal(str(r.get('expected_amount') or 0))+amt));evidence.append({'component':'CLIENT_MEAL_PAID_TIME','minutes':mins,'rate':ordinary_rate,'amount':float(amt),'clause':'27.1(c)'});flags=[x for x in str(out.at[i,'review_flags'] or '').split('; ') if x and x!='MEAL_BREAK_REVIEW'];out.at[i,'review_flags']='; '.join(flags);out.at[i,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
        elif mode=='WORKED_THROUGH':
            scheduled=_dt(ev.get('scheduled_break_start'));actual=_dt(ev.get('actual_break_start')) or end
            if scheduled is None or actual<=scheduled:_review(out,i,'WORKED_THROUGH_MEAL_TIMES_INVALID');continue
            if scheduled.date()!=actual.date():_review(out,i,'WORKED_THROUGH_MEAL_CROSS_MIDNIGHT_REVIEW');continue
            cond=lib.conditions(r.get('award_reference_date') or start)
            if not cond or not isinstance(cond.get('overtime'),dict):_review(out,i,'WORKED_THROUGH_MEAL_CONDITION_PACK_MISSING');continue
            affected=(actual-scheduled).total_seconds()/3600;deducted=pd.to_numeric(pd.Series([ev.get('deducted_break_minutes')]),errors='coerce').iloc[0];deducted=0.0 if pd.isna(deducted) else float(deducted)/60
            day=_day_type(scheduled.date(),r.get('state'),holidays,r.get('holiday_location_key'));mult=_ot_multiplier(cond,emp_type,r.get('work_group') or 'OTHER',day,0);ot_rate=effective_hourly_rate(base,mult)
            ordinary_rate=None
            for x in evidence:
                if isinstance(x,dict) and x.get('component')=='ORDINARY_OR_PENALTY' and str(x.get('date'))==str(scheduled.date()):ordinary_rate=x.get('effective_hourly_rate');break
            if ordinary_rate is None:_review(out,i,'WORKED_THROUGH_MEAL_ORDINARY_RATE_EVIDENCE_MISSING');continue
            ordinary_rate=float(ordinary_rate);already_paid=max(0,affected-deducted);delta=line_amount(deducted,ot_rate)+money(Decimal(str(already_paid))*(Decimal(str(ot_rate))-Decimal(str(ordinary_rate))))
            out.at[i,'expected_amount']=float(money(Decimal(str(r.get('expected_amount') or 0))+delta));evidence.append({'component':'WORKED_THROUGH_MEAL_OVERTIME','affected_hours':round(affected,4),'deducted_hours_restored':round(deducted,4),'overtime_rate':float(ot_rate),'ordinary_rate_replaced':ordinary_rate,'amount':float(money(delta)),'clause':'27.1(b)'});flags=[x for x in str(out.at[i,'review_flags'] or '').split('; ') if x and x!='MEAL_BREAK_REVIEW'];out.at[i,'review_flags']='; '.join(flags);out.at[i,'calculation_evidence']=json.dumps(evidence,default=str,separators=(',',':'))
        else:_review(out,i,f'UNKNOWN_MEAL_EVENT_MODE:{mode}')
    return out
