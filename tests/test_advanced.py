from pathlib import Path
import pandas as pd
from schads_audit.rules import RuleLibrary
from schads_audit.roster_overtime import normalize_rosters,attach_rosters,apply_rostered_and_daily_overtime
from schads_audit.supplemental import calculate_supplemental_events,merge_event_adjustments_into_entitlements

ROOT=Path(__file__).resolve().parents[1];LIB=RuleLibrary(ROOT/'rules/MA000100')
def holidays():return pd.DataFrame(columns=['state','holiday_date','holiday_name'])
def test_roster_explicit_match():
    ts=pd.DataFrame([{'timesheet_id':'T1','employee_id':'E1','rostered_shift_id':'R1','start_datetime':'2026-08-03 08:00','end_datetime':'2026-08-03 18:00'}]);r=normalize_rosters([{'id':'R1','member_id':'E1','start_time':'2026-08-03 09:00','end_time':'2026-08-03 17:00','breaks':[]}]);assert attach_rosters(ts,r).iloc[0].rostered_shift_match_status=='EXPLICIT_ID'
def test_full_time_rostered_overtime():
    ts=pd.DataFrame([{'timesheet_id':'T1','employee_id':'E1','start_datetime':'2026-08-03 08:00','end_datetime':'2026-08-03 18:00','rostered_start_datetime':'2026-08-03 09:00','rostered_end_datetime':'2026-08-03 17:00','rostered_shift_match_status':'EXPLICIT_ID'}]);d=pd.DataFrame([{'timesheet_id':'T1','employee_id':'E1','employee_name':'X','employment_type':'FULL_TIME','classification_code':'SACS-L2-P3','work_group':'DISABILITY_SERVICES','state':'WA','award_reference_date':'2026-08-03','shift_start':'2026-08-03 08:00','shift_end':'2026-08-03 18:00','worked_hours':10.0,'base_hourly_rate':38.50,'expected_amount':385.00,'entitlement_status':'CALCULATED','review_flags':'','calculation_evidence':'[]','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'}]);assert apply_rostered_and_daily_overtime(d,ts,holidays(),LIB).iloc[0].expected_amount==423.50
def test_casual_daily_overtime():
    ts=pd.DataFrame([{'timesheet_id':'T1','employee_id':'E1','start_datetime':'2026-08-03 07:00','end_datetime':'2026-08-03 18:00','break_units':0}]);d=pd.DataFrame([{'timesheet_id':'T1','employee_id':'E1','employment_type':'CASUAL','classification_code':'SACS-L2-P3','work_group':'DISABILITY_SERVICES','state':'WA','award_reference_date':'2026-08-03','shift_start':'2026-08-03 07:00','shift_end':'2026-08-03 18:00','worked_hours':11.0,'base_hourly_rate':38.50,'expected_amount':529.43,'entitlement_status':'CALCULATED','review_flags':'','calculation_evidence':'[]','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16'}]);assert apply_rostered_and_daily_overtime(d,ts,holidays(),LIB).iloc[0].expected_amount==548.68
def context():
    return pd.DataFrame([{'employee_id':'E1','employee_name':'X','employment_type_current':'CASUAL','state':'WA','work_group':'DISABILITY_SERVICES'}]),pd.DataFrame([{'employee_id':'E1','effective_from':'2020-01-01','classification_code':'SACS-L2-P3'}])
def test_recall_two_hour_minimum():
    e,c=context();events=pd.DataFrame([{'event_id':'A','employee_id':'E1','event_type':'RECALL_WORKPLACE','start_datetime':'2026-08-03 21:00','end_datetime':'2026-08-03 21:30','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','employment_type':'CASUAL','work_group':'DISABILITY_SERVICES','state':'WA'}]);o=calculate_supplemental_events(events,e,c,holidays(),LIB);assert o.iloc[0].expected_adjustment==134.76 and o.iloc[0].event_status=='CALCULATED'
def test_sleepover_active_one_hour_minimum():
    e,c=context();events=pd.DataFrame([{'event_id':'A','employee_id':'E1','event_type':'SLEEPOVER_ACTIVE','start_datetime':'2026-08-04 01:00','end_datetime':'2026-08-04 01:30','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','employment_type':'CASUAL','work_group':'DISABILITY_SERVICES','state':'WA'}]);assert calculate_supplemental_events(events,e,c,holidays(),LIB).iloc[0].expected_adjustment==67.38
def test_home_care_2023_rate_family():
    r,p=LIB.rate('HC-DIS-L2-P1','2023-08-01');assert r['base_hourly_rate']==25.66 and p['classification_family']=='HOME_CARE_DISABILITY'
def test_home_care_2024_rate_family():
    r,p=LIB.rate('HC-DIS-L2-P1','2024-08-01');assert r['base_hourly_rate']==26.62 and p['classification_family']=='HOME_CARE_DISABILITY'
def test_merge_supplemental_event():
    d=pd.DataFrame([{'timesheet_id':'T1','employee_id':'E1','employee_name':'X','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','expected_amount':100.0,'entitlement_status':'CALCULATED'}]);ev=pd.DataFrame([{'event_id':'A','employee_id':'E1','employee_name':'X','pay_period_start':'2026-08-03','pay_period_end':'2026-08-16','expected_adjustment':25.66,'event_status':'CALCULATED','review_flags':'','calculation_evidence':'[]'}]);o=merge_event_adjustments_into_entitlements(d,ev);assert len(o)==2 and round(o.expected_amount.sum(),2)==125.66
