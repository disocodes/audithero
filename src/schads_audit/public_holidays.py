def australian_public_holidays(start_date,end_date,states=('WA','NSW','VIC','QLD','SA','TAS','ACT','NT')):
    import holidays
    rows=[];a=int(str(start_date)[:4]);b=int(str(end_date)[:4])
    for state in states:
        cal=holidays.Australia(subdiv=state,years=range(a,b+1))
        for dt,name in cal.items():
            if str(start_date)[:10]<=dt.isoformat()<=str(end_date)[:10]:rows.append({'state':state,'holiday_date':dt.isoformat(),'holiday_name':name,'source':'python-holidays'})
    return rows
