from __future__ import annotations
from decimal import Decimal
import json
import pandas as pd

from .money import money,effective_hourly_rate,line_amount
from .roster_overtime import _day_type,_ot_multiplier


def _dt(v):
    x=pd.to_datetime(v,errors='coerce')
    return None if pd.isna(x) else x


def _bool(v):
    if isinstance(v,bool):return v
    return str(v).strip().lower() in {'1','true','yes','y'}


def audit_toil_register(register,employees,classifications,holidays,lib,audit_end_date=None):
    """Audit clause 28.2 time-off-instead-of-overtime agreements.

    The register is intentionally explicit because each amount of overtime to be
    taken as time off must be the subject of a written agreement. Where payment
    becomes due, the overtime multiplier is the one applicable to the overtime
    when worked, while the base rate is selected at the payment date as required
    by clauses 28.2(e), (f) and (j).
    """
    if register is None or register.empty:return pd.DataFrame()
    emp_index={str(r['employee_id']):r.to_dict() for _,r in employees.iterrows()} if employees is not None and not employees.empty else {}
    audit_end=_dt(audit_end_date) or pd.Timestamp.utcnow();rows=[]
    for _,r0 in register.iterrows():
        r=r0.to_dict();flags=[];evidence=[];eid=str(r.get('employee_id'));worked=_dt(r.get('overtime_datetime'));hours=float(r.get('overtime_hours') or 0);taken=float(r.get('time_off_hours') or 0);taken_date=_dt(r.get('time_off_date'));agreement_date=_dt(r.get('agreement_date'))
        if worked is None or hours<=0:flags.append('TOIL_OVERTIME_FACTS_MISSING')
        if not _bool(r.get('written_agreement')) or agreement_date is None:flags.append('TOIL_WRITTEN_AGREEMENT_MISSING')
        if taken>hours+1e-9:flags.append('TOIL_TIME_OFF_EXCEEDS_OVERTIME_HOURS')
        due_date=worked+pd.DateOffset(months=3) if worked is not None else None
        if taken_date is not None and due_date is not None and taken_date>due_date:flags.append('TOIL_TAKEN_AFTER_3_MONTH_LIMIT')
        remaining=max(0,hours-taken)
        payment_request=_dt(r.get('payment_requested_date'));termination=_dt(r.get('employment_end_date'));payment_date=_dt(r.get('payment_date')) or payment_request or termination
        payment_due=False
        reason=None
        if remaining>0 and payment_request is not None:
            payment_due=True;reason='EMPLOYEE_REQUEST'
        elif remaining>0 and termination is not None:
            payment_due=True;reason='TERMINATION'
        elif remaining>0 and due_date is not None and audit_end>=due_date:
            payment_due=True;reason='THREE_MONTH_EXPIRY';payment_date=payment_date or due_date
        expected=Decimal('0')
        if payment_due:
            code=r.get('classification_code')
            if not code and classifications is not None and not classifications.empty and worked is not None:
                q=classifications[classifications['employee_id'].astype(str)==eid].copy();q['_s']=pd.to_datetime(q['effective_from'],errors='coerce');q=q[q['_s']<=worked]
                if not q.empty:code=q.sort_values('_s',ascending=False).iloc[0].get('classification_code')
            if not code or payment_date is None or worked is None:
                flags.append('TOIL_PAYMENT_RATE_FACTS_MISSING')
            else:
                rate,_=lib.rate(code,payment_date);cond=lib.conditions(worked);emp=emp_index.get(eid,{});emp_type=str(r.get('employment_type') or emp.get('employment_type_current') or '').upper().replace(' ','_');emp_type='CASUAL' if 'CASUAL' in emp_type else 'PART_TIME' if 'PART' in emp_type else 'FULL_TIME' if 'FULL' in emp_type else 'UNKNOWN';work_group=str(r.get('work_group') or emp.get('work_group') or 'OTHER');state=r.get('state') or emp.get('state')
                if not rate or not cond or emp_type=='UNKNOWN':flags.append('TOIL_PAYMENT_RATE_FACTS_MISSING')
                else:
                    day=_day_type(worked.date(),state,holidays,r.get('holiday_location_key'));mult=_ot_multiplier(cond,emp_type,work_group,day,0);base=float(rate['base_hourly_rate']);er=effective_hourly_rate(base,mult);amt=line_amount(remaining,er);expected+=amt;evidence.append({'component':'TOIL_PAYMENT_DUE','reason':reason,'remaining_hours':remaining,'overtime_date':str(worked),'payment_rate_date':str(payment_date),'multiplier':mult,'base_rate_at_payment':base,'effective_hourly_rate':float(er),'amount':float(amt),'clause':'28.2'})
        elif remaining>0 and due_date is not None:
            evidence.append({'component':'TOIL_OUTSTANDING','remaining_hours':remaining,'deadline':str(due_date),'clause':'28.2(d)'})
        status='REQUIRES_REVIEW' if flags else 'PAYMENT_DUE' if payment_due and remaining>0 else 'COMPLIANT_OR_OPEN'
        rows.append({'toil_agreement_id':r.get('agreement_id'),'employee_id':eid,'employee_name':emp_index.get(eid,{}).get('employee_name'),'overtime_datetime':worked,'overtime_hours':hours,'time_off_hours':taken,'remaining_hours':remaining,'deadline':due_date,'payment_date':payment_date,'payment_reason':reason,'expected_adjustment':float(money(expected)),'status':status,'review_flags':'; '.join(sorted(set(flags))),'calculation_evidence':json.dumps(evidence,default=str,separators=(',',':')),'pay_period_start':_dt(r.get('payment_pay_period_start')),'pay_period_end':_dt(r.get('payment_pay_period_end'))})
    return pd.DataFrame(rows)


def merge_toil_adjustments(detail,toil_findings):
    if toil_findings is None or toil_findings.empty:return detail
    rows=[]
    for _,r in toil_findings.iterrows():
        actionable=r.get('status')=='PAYMENT_DUE' and _dt(r.get('pay_period_start')) is not None and _dt(r.get('pay_period_end')) is not None
        rows.append({'timesheet_id':f"TOIL:{r.get('toil_agreement_id')}",'employee_id':r.get('employee_id'),'employee_name':r.get('employee_name'),'employment_type':None,'classification_code':None,'work_group':None,'state':None,'pay_period_start':r.get('pay_period_start'),'pay_period_end':r.get('pay_period_end'),'award_reference_date':r.get('payment_date'),'shift_start':pd.NaT,'shift_end':pd.NaT,'worked_hours':0.0,'base_hourly_rate':None,'expected_amount':r.get('expected_adjustment') if actionable else None,'entitlement_status':'CALCULATED' if actionable else 'REQUIRES_REVIEW','review_flags':r.get('review_flags') if actionable else (str(r.get('review_flags') or '')+'; TOIL_PAYMENT_PAY_PERIOD_REQUIRED').strip('; '),'calculation_evidence':r.get('calculation_evidence')})
    ev=pd.DataFrame(rows)
    return pd.concat([detail,ev],ignore_index=True,sort=False) if detail is not None and not detail.empty else ev
