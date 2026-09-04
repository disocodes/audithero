from __future__ import annotations
import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value


def _dt(v):
    x = parse_datetime_value(v)
    return None if pd.isna(x) else x


def _flag(existing, flag):
    parts=[x for x in str(existing or '').split('; ') if x]
    parts.append(flag)
    return '; '.join(sorted(set(parts)))


def _effective(history, employee_id, when):
    if history is None or history.empty or when is None:
        return None
    q=history[history['employee_id'].astype(str)==str(employee_id)].copy()
    if q.empty:return None
    q['_from']=parse_datetime_series(q['effective_from'])
    q['_to']=parse_datetime_series(q['effective_to']) if 'effective_to' in q.columns else pd.NaT
    q=q[(q['_from']<=when)&(q['_to'].isna()|(q['_to']>=when))]
    return None if q.empty else q.sort_values('_from',ascending=False).iloc[0].to_dict()


def apply_instrument_history(detail, instrument_history):
    """Attach the industrial instrument in force for each historical shift.

    Award calculations remain available as an Award comparator. Where an EA,
    IFA, salary package or other arrangement applies, the shift is forced to
    REQUIRES_REVIEW so the Award comparator is never presented as the final
    contractual entitlement.
    """
    if detail is None or detail.empty:return detail
    out=detail.copy()
    for col in ('industrial_instrument_type','industrial_instrument_name','instrument_reference','instrument_coverage_status'):
        if col not in out.columns:out[col]=None
    for idx,r in out.iterrows():
        when=_dt(r.get('shift_start')) or _dt(r.get('award_reference_date'))
        row=_effective(instrument_history,r.get('employee_id'),when)
        if not row:
            out.at[idx,'industrial_instrument_type']='AWARD_ASSUMED'
            out.at[idx,'instrument_coverage_status']='NO_CONTROL_REGISTER_MATCH'
            out.at[idx,'review_flags']=_flag(r.get('review_flags'),'INDUSTRIAL_INSTRUMENT_HISTORY_NOT_VERIFIED')
            out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
            continue
        typ=str(row.get('instrument_type') or 'AWARD').upper().strip()
        out.at[idx,'industrial_instrument_type']=typ
        out.at[idx,'industrial_instrument_name']=row.get('instrument_name')
        out.at[idx,'instrument_reference']=row.get('document_reference') or row.get('instrument_reference')
        out.at[idx,'instrument_coverage_status']='CONTROLLED_REGISTER_MATCH'
        if typ in ('AWARD','MODERN_AWARD'):
            if str(row.get('award_code') or 'MA000100').upper()!='MA000100':
                out.at[idx,'review_flags']=_flag(out.at[idx,'review_flags'],'NON_SCHADS_AWARD_APPLIES')
                out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
        elif typ in ('ENTERPRISE_AGREEMENT','EA'):
            out.at[idx,'review_flags']=_flag(out.at[idx,'review_flags'],'ENTERPRISE_AGREEMENT_APPLIES_AWARD_IS_COMPARATOR_ONLY')
            out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
        elif typ=='IFA':
            out.at[idx,'review_flags']=_flag(out.at[idx,'review_flags'],'IFA_APPLIES_BETTER_OFF_OVERALL_REVIEW')
            out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
        elif typ in ('SALARY_PACKAGE','ANNUALISED_SALARY','OFFSET_ARRANGEMENT'):
            out.at[idx,'review_flags']=_flag(out.at[idx,'review_flags'],'SALARY_OR_OFFSET_ARRANGEMENT_RECONCILIATION_REQUIRED')
            out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
        else:
            out.at[idx,'review_flags']=_flag(out.at[idx,'review_flags'],f'UNKNOWN_INSTRUMENT_TYPE:{typ}')
            out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
    return out


def instrument_readiness_findings(instrument_history,start_date,end_date):
    if instrument_history is None or instrument_history.empty:
        return pd.DataFrame([{'finding_type':'INDUSTRIAL_INSTRUMENT_REGISTER','status':'MAPPING_REQUIRED','detail':'No historical industrial instrument register loaded.'}])
    rows=[]
    for _,r in instrument_history.iterrows():
        typ=str(r.get('instrument_type') or '').upper()
        status='READY' if typ in {'AWARD','MODERN_AWARD'} and str(r.get('award_code') or '').upper()=='MA000100' else 'REVIEW_REQUIRED'
        rows.append({'finding_type':'INDUSTRIAL_INSTRUMENT','source_key':r.get('employee_id'),'source_label':r.get('instrument_name'),'status':status,'detail':typ})
    return pd.DataFrame(rows)
