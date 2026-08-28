from pathlib import Path
import pandas as pd
from schads_audit.rules import RuleLibrary
from schads_audit.engine import calculate_entitlements,reconcile_pay_periods
ROOT=Path(__file__).resolve().parents[1];LIB=RuleLibrary(ROOT/'rules/MA000100')
def frames(start,end):
 employees=pd.DataFrame([{'employee_id':'E1','employee_name':'Test Employee','employment_type_current':'Casual','state':'WA','work_group':'DISABILITY_SERVICES'}]);history=pd.DataFrame([{'employee_id':'E1','start_date':'2020-01-01','end_date':None,'employment_type':'Casual'}]);cls=pd.DataFrame([{'employee_id':'E1','effective_from':'2020-01-01','classification_code':'SACS-L2-P3'}]);ts=pd.DataFrame([{'timesheet_id':'T1','employee_id':'E1','start_datetime':start,'end_datetime':end,'break_units':0,'work_group':'DISABILITY_SERVICES','location_state':'WA','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'}]);hol=pd.DataFrame(columns=['state','holiday_date','holiday_name']);return employees,history,cls,ts,hol
def test_casual_saturday_2026():
 d=calculate_entitlements(*frames('2026-08-08 18:00','2026-08-08 22:00'),LIB);assert d.iloc[0].expected_amount==269.52
def test_historical_2024_rate():
 e,h,c,t,hol=frames('2024-08-10 18:00','2024-08-10 22:00');t['pay_period_start']='2024-08-05';t['pay_period_end']='2024-08-18';d=calculate_entitlements(e,h,c,t,hol,LIB);assert d.iloc[0].expected_amount==248.56
def test_underpayment_reconciliation():
 d=calculate_entitlements(*frames('2026-08-08 18:00','2026-08-08 22:00'),LIB);p=pd.DataFrame([{'employee_id':'E1','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','pay_category':'Ordinary Hours','pay_category_id':None,'amount':200.0}]);r=reconcile_pay_periods(d,p,{'Ordinary Hours':{'audit_treatment':'AUDITABLE_WORK'}});assert r.iloc[0].status=='UNDERPAID' and r.iloc[0].variance_actual_minus_expected==-69.52
