from .dates import as_date, parse_datetime_series


def australian_public_holidays(start_date,end_date,states=('WA','NSW','VIC','QLD','SA','TAS','ACT','NT')):
    import holidays
    start=as_date(start_date);end=as_date(end_date)
    rows=[]
    for state in states:
        cal=holidays.Australia(subdiv=state,years=range(start.year,end.year+1))
        for dt,name in cal.items():
            if start<=dt<=end:
                rows.append({'state':state,'holiday_date':dt.isoformat(),'holiday_name':name,'holiday_location_key':None,'holiday_scope':'STATEWIDE','source':'python-holidays'})
    return rows


def normalise_public_holiday_overrides(df):
    """Normalise controlled holiday overrides using Australian date conventions.

    `holiday_location_key` is optional. Blank means statewide; a value means the
    holiday only applies to timesheets mapped to that same location key.
    """
    import pandas as pd
    if df is None or df.empty:return pd.DataFrame(columns=['state','holiday_date','holiday_name','holiday_location_key','holiday_scope','source'])
    out=df.copy()
    for c in ('state','holiday_date','holiday_name'):
        if c not in out.columns:raise ValueError(f'Public holiday override missing required column: {c}')
    original=out['holiday_date'].copy();out['holiday_date']=parse_datetime_series(original)
    invalid=original.notna() & original.astype(str).str.strip().ne('') & out['holiday_date'].isna()
    if invalid.any():raise ValueError(f"Public holiday override contains {int(invalid.sum())} invalid holiday_date value(s)")
    out['holiday_date']=out['holiday_date'].dt.date
    if 'holiday_location_key' not in out.columns:out['holiday_location_key']=None
    if 'holiday_scope' not in out.columns:out['holiday_scope']=out['holiday_location_key'].apply(lambda x:'LOCAL' if pd.notna(x) and str(x).strip() else 'STATEWIDE')
    if 'source' not in out.columns:out['source']='manual_override'
    out['holiday_location_key']=out['holiday_location_key'].where(out['holiday_location_key'].notna(),None)
    return out[['state','holiday_date','holiday_name','holiday_location_key','holiday_scope','source']]
