from pathlib import Path
import pandas as pd
from schads_audit.rules import RuleLibrary
from schads_audit.engine import calculate_entitlements
from schads_audit.roster_overtime import allocate_period_overtime

ROOT=Path(__file__).resolve().parents[1]
LIB=RuleLibrary(ROOT/'rules/MA000100')


def frames(timesheets):
    employees=pd.DataFrame([{'employee_id':'E1','employee_name':'Test','employment_type_current':'Casual','state':'WA','work_group':'DISABILITY_SERVICES'}])
    hist=pd.DataFrame([{'employee_id':'E1','start_date':'2020-01-01','end_date':None,'employment_type':'Casual'}])
    cls=pd.DataFrame([{'employee_id':'E1','effective_from':'2020-01-01','classification_code':'SACS-L2-P3'}])
    return employees,hist,cls,pd.DataFrame(timesheets)


def test_local_public_holiday_only_applies_to_matching_location():
    ts=[
      {'timesheet_id':'A','employee_id':'E1','start_datetime':'2026-09-28 09:00','end_datetime':'2026-09-28 13:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','holiday_location_key':'KUNUNURRA','pay_period_start':'2026-09-21','pay_period_end':'2026-10-04'},
      {'timesheet_id':'B','employee_id':'E1','start_datetime':'2026-09-28 14:00','end_datetime':'2026-09-28 18:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','holiday_location_key':'PERTH','pay_period_start':'2026-09-21','pay_period_end':'2026-10-04'}]
    e,h,c,t=frames(ts)
    holidays=pd.DataFrame([{'state':'WA','holiday_date':'2026-09-28','holiday_name':'Local Holiday','holiday_location_key':'KUNUNURRA','holiday_scope':'LOCAL','source':'test'}])
    d=calculate_entitlements(e,h,c,t,holidays,LIB)
    assert 'PUBLIC_HOLIDAY' in d.loc[d.timesheet_id=='A','calculation_evidence'].iloc[0]
    assert 'PUBLIC_HOLIDAY' not in d.loc[d.timesheet_id=='B','calculation_evidence'].iloc[0]


def test_weekly_overtime_reprices_unique_excess():
    ts=[]
    for day in range(3,8):
        ts.append({'timesheet_id':f'T{day}','employee_id':'E1','start_datetime':f'2026-08-{day:02d} 08:00','end_datetime':f'2026-08-{day:02d} 16:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-09'})
    e,h,c,t=frames(ts)
    holidays=pd.DataFrame(columns=['state','holiday_date','holiday_name','holiday_location_key'])
    d=calculate_entitlements(e,h,c,t,holidays,LIB)
    out=allocate_period_overtime(d,holidays,LIB)
    assert any('PERIOD_OVERTIME_REPRICE' in x for x in out.calculation_evidence)
