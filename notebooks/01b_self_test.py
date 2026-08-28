# Databricks notebook source
# MAGIC %pip install "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read())
import pandas as pd
from schads_audit.rules import RuleLibrary
from schads_audit.engine import calculate_entitlements
from schads_audit.broken_sleepover import group_broken_shifts,apply_broken_shift_rules
from schads_audit.roster_overtime import allocate_period_overtime

lib=RuleLibrary(ROOT/'rules/MA000100')
passed=[]

def ok(name,condition,detail=''):
    if not condition:raise AssertionError(f'{name} failed: {detail}')
    passed.append(name);print(f'✓ {name}')

errors=lib.validate();ok('rule library validation',errors==[],errors)
r,p=lib.rate('SACS-L2-P3','2024-09-01');ok('historical 2024 SACS rate',r and r['base_hourly_rate']==35.51,r)
r,p=lib.rate('SACS-L2-P3','2026-08-01');ok('current 2026 SACS rate',r and r['base_hourly_rate']==38.50,r)

employees=pd.DataFrame([{'employee_id':'E1','employee_name':'Test','employment_type_current':'Casual','state':'WA','work_group':'DISABILITY_SERVICES'}])
history=pd.DataFrame([{'employee_id':'E1','start_date':'2020-01-01','end_date':None,'employment_type':'Casual'}])
classes=pd.DataFrame([{'employee_id':'E1','effective_from':'2020-01-01','classification_code':'SACS-L2-P3'}])
empty_holidays=pd.DataFrame(columns=['state','holiday_date','holiday_name','holiday_location_key'])

sat=pd.DataFrame([{'timesheet_id':'SAT','employee_id':'E1','start_datetime':'2026-08-08 18:00','end_datetime':'2026-08-08 22:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'}])
d=calculate_entitlements(employees,history,classes,sat,empty_holidays,lib);ok('casual Saturday calculation',float(d.iloc[0].expected_amount)==269.52,d.iloc[0].to_dict())

sleep=pd.DataFrame([{'timesheet_id':'SO','employee_id':'E1','start_datetime':'2026-08-03 22:00','end_datetime':'2026-08-04 06:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','is_sleepover':True}])
d=calculate_entitlements(employees,history,classes,sleep,empty_holidays,lib);ok('sleepover is not ordinary worked hours',float(d.iloc[0].worked_hours)==0 and float(d.iloc[0].sleepover_span_hours)==8,d.iloc[0].to_dict());ok('sleepover allowance evidence','SLEEPOVER_ALLOWANCE' in d.iloc[0].calculation_evidence,d.iloc[0].calculation_evidence)

local_ts=pd.DataFrame([
 {'timesheet_id':'LOCAL','employee_id':'E1','start_datetime':'2026-09-28 09:00','end_datetime':'2026-09-28 13:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','holiday_location_key':'KUNUNURRA','pay_period_start':'2026-09-21','pay_period_end':'2026-10-04'},
 {'timesheet_id':'OTHER','employee_id':'E1','start_datetime':'2026-09-28 14:00','end_datetime':'2026-09-28 18:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','holiday_location_key':'PERTH','pay_period_start':'2026-09-21','pay_period_end':'2026-10-04'}])
local_holidays=pd.DataFrame([{'state':'WA','holiday_date':'2026-09-28','holiday_name':'Local Holiday','holiday_location_key':'KUNUNURRA','holiday_scope':'LOCAL','source':'self_test'}]);d=calculate_entitlements(employees,history,classes,local_ts,local_holidays,lib);ev=dict(zip(d.timesheet_id,d.calculation_evidence));ok('local holiday applies to matching location','PUBLIC_HOLIDAY' in ev['LOCAL']);ok('local holiday does not leak statewide','PUBLIC_HOLIDAY' not in ev['OTHER'])

broken=pd.DataFrame([
 {'timesheet_id':'B1','employee_id':'E1','start_datetime':'2026-08-03 07:00','end_datetime':'2026-08-03 09:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'},
 {'timesheet_id':'B2','employee_id':'E1','start_datetime':'2026-08-03 16:00','end_datetime':'2026-08-03 19:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'}]);broken=group_broken_shifts(broken);d=calculate_entitlements(employees,history,classes,broken,empty_holidays,lib);d=apply_broken_shift_rules(d,broken,lib);ok('broken shift grouped',broken.broken_shift_group_id.notna().all());ok('broken shift allowance applied',any('BROKEN_SHIFT_ALLOWANCE' in x for x in d.calculation_evidence))

week=[]
for day in range(3,8):
    week.append({'timesheet_id':f'W{day}','employee_id':'E1','start_datetime':f'2026-08-{day:02d} 08:00','end_datetime':f'2026-08-{day:02d} 16:00','break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-09'})
d=calculate_entitlements(employees,history,classes,pd.DataFrame(week),empty_holidays,lib);d=allocate_period_overtime(d,empty_holidays,lib);ok('weekly threshold overtime allocation',any('PERIOD_OVERTIME_REPRICE' in x for x in d.calculation_evidence))

print(f'\nAuditHero self-test complete: {len(passed)} checks passed.')
