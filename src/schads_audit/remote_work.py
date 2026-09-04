from __future__ import annotations
from datetime import time
import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value


def _dt(v):
    x=parse_datetime_value(v)
    return None if pd.isna(x) else x


def _bool(v):
    if isinstance(v,bool):return v
    return str(v).strip().lower() in {'1','true','yes','y'}


def _minimum_hours(row,start):
    if _bool(row.get('training_or_meeting')) or not _bool(row.get('on_call')):return 1.0
    return 0.5 if start.time()>=time(22) or start.time()<time(6) else 0.25


def aggregate_remote_work_events(events):
    """Collapse multiple remote-work instances that fall within one minimum-payment window.

    Clause 25.10(c)(iii) says multiple instances within the applicable minimum
    payment period trigger only one minimum period. The result retains a review
    flag when overlapping/gapped facts make a larger-than-minimum amount
    ambiguous rather than manufacturing continuous work.
    """
    if events is None or events.empty:return events
    remote=events[events['event_type'].astype(str).str.upper()=='REMOTE_WORK'].copy()
    other=events[events['event_type'].astype(str).str.upper()!='REMOTE_WORK'].copy()
    if remote.empty:return events
    remote['_s']=parse_datetime_series(remote['start_datetime']);remote['_e']=parse_datetime_series(remote['end_datetime'])
    outputs=[]
    for (eid,day),g in remote.dropna(subset=['_s']).groupby([remote['employee_id'].astype(str),remote['_s'].dt.date]):
        g=g.sort_values('_s');clusters=[];current=[];anchor=None;window=None
        for idx,r in g.iterrows():
            s=r['_s'];minh=_minimum_hours(r,s)
            signature=(_bool(r.get('on_call')),_bool(r.get('training_or_meeting')),minh)
            if not current:
                current=[(idx,r,signature)];anchor=s;window=minh;continue
            if signature==current[0][2] and s < anchor+pd.Timedelta(hours=window):
                current.append((idx,r,signature))
            else:
                clusters.append(current);current=[(idx,r,signature)];anchor=s;window=minh
        if current:clusters.append(current)
        for n,cluster in enumerate(clusters,1):
            rows=[x[1] for x in cluster];first=rows[0].to_dict();starts=[r['_s'] for r in rows];ends=[r['_e'] for r in rows if not pd.isna(r['_e'])]
            min_hours=cluster[0][2][2];actual=0.0;intervals=[]
            for r in rows:
                s=r['_s'];e=r['_e']
                if pd.isna(e):continue
                actual+=max(0,(e-s).total_seconds()/3600);intervals.append((s,e))
            first['event_id']=first.get('event_id') or f'REMOTE:{eid}:{day}:{n}'
            if len(rows)>1:first['event_id']=f'REMOTE_GROUP:{eid}:{day}:{n}'
            first['start_datetime']=min(starts);first['end_datetime']=max(ends) if ends else first['start_datetime'];first['hours']=actual;first['remote_minimum_hours']=min_hours;first['remote_instance_count']=len(rows)
            first['remote_source_event_ids']=';'.join(str(r.get('event_id') or '') for r in rows)
            separated=False
            if len(intervals)>1:
                intervals=sorted(intervals)
                separated=any(intervals[i][0]>intervals[i-1][1] for i in range(1,len(intervals)))
            first['remote_aggregation_review']='REMOTE_MULTI_INSTANCE_CONTINUITY_REVIEW' if separated and actual>min_hours else ''
            outputs.append(first)
    combined=pd.concat([other,pd.DataFrame(outputs)],ignore_index=True,sort=False)
    return combined.drop(columns=[c for c in ('_s','_e') if c in combined.columns])
