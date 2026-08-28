# AuditHero Fabric native self-test
import pandas as pd
from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.engine import calculate_entitlements
from schads_audit.broken_sleepover import group_broken_shifts, group_sleepovers

lib = bundled_rule_library()
errors = lib.validate()
assert not errors, errors

# Current casual Saturday regression.
employees = pd.DataFrame([{"employee_id":"E1","employee_name":"Test","employment_type_current":"Casual","state":"WA","work_group":"DISABILITY_SERVICES"}])
history = pd.DataFrame([{"employee_id":"E1","start_date":"2020-01-01","end_date":None,"employment_type":"Casual"}])
cls = pd.DataFrame([{"employee_id":"E1","effective_from":"2020-01-01","classification_code":"SACS-L2-P3"}])
ts = pd.DataFrame([{"timesheet_id":"T1","employee_id":"E1","start_datetime":"2026-08-08 18:00","end_datetime":"2026-08-08 22:00","break_units":0,"work_group":"DISABILITY_SERVICES","location_state":"WA","pay_period_start":"2026-08-03","pay_period_end":"2026-08-16"}])
holidays = pd.DataFrame(columns=["state","holiday_date","holiday_name","holiday_location_key"])
detail = calculate_entitlements(employees,history,cls,ts,holidays,lib)
assert float(detail.iloc[0]["expected_amount"]) == 269.52

# Historical rate selection.
rate, pack = lib.rate("SACS-L2-P3", "2024-08-05")
assert float(rate["base_hourly_rate"]) == 35.51
assert pack["operative_date"] == "2024-07-01"

# Sleepover must be allowance-only, not eight ordinary worked hours.
sleep = pd.DataFrame([{"timesheet_id":"S1","employee_id":"E1","start_datetime":"2026-08-03 22:00","end_datetime":"2026-08-04 06:00","break_units":0,"work_group":"DISABILITY_SERVICES","location_state":"WA","pay_period_start":"2026-08-03","pay_period_end":"2026-08-16","is_sleepover":True}])
sleep = group_sleepovers(sleep)
sleep_detail = calculate_entitlements(employees,history,cls,sleep,holidays,lib)
assert float(sleep_detail.iloc[0]["worked_hours"]) == 0.0
assert float(sleep_detail.iloc[0]["sleepover_span_hours"]) == 8.0
assert "SLEEPOVER_ALLOWANCE" in sleep_detail.iloc[0]["calculation_evidence"]

# Broken-shift inference.
broken = pd.DataFrame([
 {"timesheet_id":"B1","employee_id":"E1","start_datetime":"2026-08-03 07:00","end_datetime":"2026-08-03 09:00","work_group":"DISABILITY_SERVICES"},
 {"timesheet_id":"B2","employee_id":"E1","start_datetime":"2026-08-03 16:00","end_datetime":"2026-08-03 19:00","work_group":"DISABILITY_SERVICES"},
])
broken = group_broken_shifts(broken)
assert broken["broken_shift_group_id"].notna().all()

# Rule tables loaded into Lakehouse by setup.
assert spark.table("ref.rates").count() > 0
assert spark.table("ref.conditions").count() > 0
assert spark.table("ref.allowances").count() > 0

print("AuditHero Fabric self-test PASSED")
notebookutils.notebook.exit("success")
