def australian_public_holidays(start_date,end_date,states=('WA','NSW','VIC','QLD','SA','TAS','ACT','NT')):
    import holidays
    rows=[];a=int(str(start_date)[:4]);b=int(str(end_date)[:4])
    for state in states:
        cal=holidays.Australia(subdiv=state,years=range(a,b+1))
        for dt,name in cal.items():
            if str(start_date)[:10]<=dt.isoformat()<=str(end_date)[:10]:
                rows.append({'state':state,'holiday_date':dt.isoformat(),'holiday_name':name,'holiday_location_key':None,'holiday_scope':'STATEWIDE','source':'python-holidays'})
    return rows


def normalise_public_holiday_overrides(df):
    """Normalise controlled holiday overrides.

    `holiday_location_key` is optional. Blank means statewide; a value means the
    holiday only applies to timesheets mapped to that same location key.
    """
    import pandas as pd
    if df is None or df.empty:return pd.DataFrame(columns=['state','holiday_date','holiday_name','holiday_location_key','holiday_scope','source'])
    out=df.copy()
    for c in ('state','holiday_date','holiday_name'):
        if c not in out.columns:raise ValueError(f'Public holiday override missing required column: {c}')
    if 'holiday_location_key' not in out.columns:out['holiday_location_key']=None
    if 'holiday_scope' not in out.columns:out['holiday_scope']=out['holiday_location_key'].apply(lambda x:'LOCAL' if pd.notna(x) and str(x).strip() else 'STATEWIDE')
    if 'source' not in out.columns:out['source']='manual_override'
    out['holiday_location_key']=out['holiday_location_key'].where(out['holiday_location_key'].notna(),None)
    return out[['state','holiday_date','holiday_name','holiday_location_key','holiday_scope','source']]
