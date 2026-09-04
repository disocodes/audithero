from __future__ import annotations
from datetime import datetime,time
import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value


def _dt(v):
    x=parse_datetime_value(v)
    return None if pd.isna(x) else x


def _flag(existing,flag):
    parts=[x for x in str(existing or '').split('; ') if x];parts.append(flag)
    return '; '.join(sorted(set(parts)))


def _parse_time(v):
    if v in (None,''):return None
    s=str(v).strip()
    for fmt in ('%H:%M','%H:%M:%S'):
        try:return datetime.strptime(s,fmt).time()
        except ValueError:pass
    return None


def _effective_rows(patterns,eid,when):
    if patterns is None or patterns.empty:return pd.DataFrame()
    q=patterns[patterns['employee_id'].astype(str)==str(eid)].copy()
    if q.empty:return q
    q['_from']=parse_datetime_series(q['effective_from'])
    q['_to']=parse_datetime_series(q['effective_to']) if 'effective_to' in q.columns else pd.NaT
    q=q[(q['_from']<=when)&(q['_to'].isna()|(q['_to']>=when))]
    return q


def _variation_match(variations,eid,start,end):
    if variations is None or variations.empty:return None
    q=variations[variations['employee_id'].astype(str)==str(eid)].copy()
    if q.empty:return None
    q['_date']=parse_datetime_series(q['shift_date']).dt.date
    q=q[q['_date']==start.date()]
    if q.empty:return None
    for _,r in q.iterrows():
        vs=_parse_time(r.get('start_time'));ve=_parse_time(r.get('end_time'))
        if vs is None or ve is None:return r.to_dict()
        if start.time()>=vs and end.time()<=ve:return r.to_dict()
    return None


def apply_part_time_pattern_checks(detail,patterns,variations=None):
    """Validate part-time shifts against effective written regular patterns.

    This module does not automatically convert hours outside the pattern to
    overtime. Clause 10.3 allows additional hours by agreement, so the correct
    result is an evidence finding unless a controlled variation exists.
    """
    if detail is None or detail.empty:return detail
    out=detail.copy()
    for col in ('part_time_pattern_status','part_time_pattern_reference','part_time_variation_reference'):
        if col not in out.columns:out[col]=None
    for idx,r in out.iterrows():
        if str(r.get('employment_type'))!='PART_TIME':continue
        start=_dt(r.get('shift_start'));end=_dt(r.get('shift_end'))
        if start is None or end is None:continue
        q=_effective_rows(patterns,r.get('employee_id'),start)
        if q.empty:
            out.at[idx,'part_time_pattern_status']='MISSING'
            out.at[idx,'review_flags']=_flag(r.get('review_flags'),'PT_WRITTEN_PATTERN_HISTORY_MISSING')
            out.at[idx,'entitlement_status']='REQUIRES_REVIEW';continue
        weekday=start.strftime('%A').upper()
        q=q[q['weekday'].astype(str).str.upper()==weekday]
        if q.empty:
            var=_variation_match(variations,r.get('employee_id'),start,end)
            if var:
                out.at[idx,'part_time_pattern_status']='VARIATION_MATCH'
                out.at[idx,'part_time_variation_reference']=var.get('agreement_reference')
            else:
                out.at[idx,'part_time_pattern_status']='OUTSIDE_REGULAR_PATTERN'
                out.at[idx,'review_flags']=_flag(r.get('review_flags'),'PT_ADDITIONAL_HOURS_AGREEMENT_VERIFY')
                out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
            continue
        matched=None
        for _,p in q.iterrows():
            ps=_parse_time(p.get('start_time'));pe=_parse_time(p.get('end_time'))
            if ps is None or pe is None:continue
            if start.time()>=ps and end.time()<=pe:
                matched=p.to_dict();break
        if matched:
            out.at[idx,'part_time_pattern_status']='REGULAR_PATTERN_MATCH'
            out.at[idx,'part_time_pattern_reference']=matched.get('agreement_reference')
        else:
            var=_variation_match(variations,r.get('employee_id'),start,end)
            if var:
                out.at[idx,'part_time_pattern_status']='VARIATION_MATCH'
                out.at[idx,'part_time_variation_reference']=var.get('agreement_reference')
            else:
                out.at[idx,'part_time_pattern_status']='OUTSIDE_REGULAR_PATTERN'
                out.at[idx,'review_flags']=_flag(r.get('review_flags'),'PT_ADDITIONAL_HOURS_AGREEMENT_VERIFY')
                out.at[idx,'entitlement_status']='REQUIRES_REVIEW'
    return out
