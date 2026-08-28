from pathlib import Path
import pandas as pd
from schads_audit.rules import RuleLibrary
from schads_audit.engine import calculate_entitlements
from schads_audit.broken_sleepover import group_broken_shifts,apply_broken_shift_rules,group_sleepovers,apply_sleepover_group_rules

ROOT=Path(__file__).resolve().parents[1]
LIB=RuleLibrary(ROOT/'rules/MA000100')


def base_frames(ts):
    employees=pd.DataFrame([{'employee_id':'E1','employee_name':'Test','employment_type_current':'Casual','state':'WA','work_group':'DISABILITY_SERVICES'}])
    hist=pd.DataFrame([{'employee_id':'E1','start_date':'2020-01-01','end_date':None,'employment_type':'Casual'}])
    cls=pd.DataFrame([{'employee_id':'E1','effective_from':'2020-01-01','classification_code':'SACS-L2-P3'}])
    hol=pd.DataFrame(columns=['state','holiday_date','holiday_name'])
    return employees,hist,cls,pd.DataFrame(ts),hol


def test_broken_shift_inference_and_allowance():
    ts=[
      {'timesheet_id':'A','employee_id':'E1','start_datetime':'2026-08-03 07:00','end_datetime':'2026-08-03 09:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'},
      {'timesheet_id':'B','employee_id':'E1','start_datetime':'2026-08-03 16:00','end_datetime':'2026-08-03 19:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'}]
    e,h,c,t,hol=base_frames(ts)
    t=group_broken_shifts(t)
    assert t.broken_shift_group_id.notna().all()
    d=calculate_entitlements(e,h,c,t,hol,LIB)
    d=apply_broken_shift_rules(d,t,LIB)
    assert any('BROKEN_SHIFT_ALLOWANCE' in x for x in d.calculation_evidence)


def test_sleepover_span_is_not_ordinary_worked_hours():
    ts=[{'timesheet_id':'S','employee_id':'E1','start_datetime':'2026-08-03 22:00','end_datetime':'2026-08-04 06:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','is_sleepover':True}]
    e,h,c,t,hol=base_frames(ts)
    d=calculate_entitlements(e,h,c,t,hol,LIB)
    row=d.iloc[0]
    assert row.worked_hours==0
    assert row.sleepover_span_hours==8
    assert 'SLEEPOVER_SPAN' in row.calculation_evidence
    assert 'ORDINARY_OR_PENALTY' not in row.calculation_evidence


def test_sleepover_grouping_and_minimum_before_after():
    ts=[
      {'timesheet_id':'A','employee_id':'E1','start_datetime':'2026-08-03 18:00','end_datetime':'2026-08-03 20:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','is_sleepover':False},
      {'timesheet_id':'S','employee_id':'E1','start_datetime':'2026-08-03 20:00','end_datetime':'2026-08-04 04:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','is_sleepover':True},
      {'timesheet_id':'B','employee_id':'E1','start_datetime':'2026-08-04 04:00','end_datetime':'2026-08-04 06:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','is_sleepover':False}]
    e,h,c,t,hol=base_frames(ts)
    t=group_sleepovers(t)
    assert set(t.sleepover_period_role.dropna())=={'BEFORE','SLEEPOVER','AFTER'}
    d=calculate_entitlements(e,h,c,t,hol,LIB)
    d=apply_sleepover_group_rules(d,t,LIB)
    assert any('SLEEPOVER_SURROUNDING_WORK_MINIMUM_TOPUP' in x for x in d.calculation_evidence)
