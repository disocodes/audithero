from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

def month_chunks(start_date,end_date):
    start=date.fromisoformat(str(start_date)[:10]);end=date.fromisoformat(str(end_date)[:10]);cur=start
    while cur<=end:
        next_month=(cur.replace(day=28)+timedelta(days=4)).replace(day=1)
        chunk_end=min(end,next_month-timedelta(days=1));yield cur.isoformat(),chunk_end.isoformat();cur=chunk_end+timedelta(days=1)

def recent_window(days=45,timezone="Australia/Perth"):
    now=datetime.now(ZoneInfo(timezone)).date();return (now-timedelta(days=int(days))).isoformat(),now.isoformat()

def previous_calendar_month(timezone="Australia/Perth"):
    now=datetime.now(ZoneInfo(timezone)).date();first=now.replace(day=1);last=first-timedelta(days=1);return last.replace(day=1).isoformat(),last.isoformat()
