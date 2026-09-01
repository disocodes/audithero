# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Databricks Self Test
# MAGIC
# MAGIC **Purpose:** verify representative SCHADS calculations inside the installed Databricks environment before production payroll data is used.
# MAGIC
# MAGIC Self Test uses synthetic records only. It checks historical/current rate selection, a casual Saturday, sleepover treatment, location-specific holidays, broken-shift grouping/allowance and period overtime allocation. A failed assertion indicates that the installed runtime or rule configuration requires review.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

import pandas as pd
from schads_audit.rules import RuleLibrary
from schads_audit.engine import calculate_entitlements
from schads_audit.broken_sleepover import group_broken_shifts, apply_broken_shift_rules
from schads_audit.roster_overtime import allocate_period_overtime

lib = RuleLibrary(ROOT / "rules/MA000100")
passed = []


def ok(name, condition, detail=""):
    """Record a passed check or raise an assertion containing diagnostic detail."""
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")
    passed.append(name)
    print(f"✓ {name}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Rule versions and known rates
# MAGIC
# MAGIC These checks confirm that the expected historical and current rule packs are available.
# COMMAND ----------
errors = lib.validate()
ok("rule library validation", errors == [], errors)

rate_2024, _ = lib.rate("SACS-L2-P3", "2024-09-01")
ok("historical 2024 SACS rate", rate_2024 and rate_2024["base_hourly_rate"] == 35.51, rate_2024)

rate_2026, _ = lib.rate("SACS-L2-P3", "2026-08-01")
ok("current 2026 SACS rate", rate_2026 and rate_2026["base_hourly_rate"] == 38.50, rate_2026)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Build a synthetic employee
# MAGIC
# MAGIC A single synthetic employee is reused across the following test cases. No production employee data is read.
# COMMAND ----------
employees = pd.DataFrame([
    {"employee_id": "E1", "employee_name": "Test", "employment_type_current": "Casual", "state": "WA", "work_group": "DISABILITY_SERVICES"}
])
history = pd.DataFrame([
    {"employee_id": "E1", "start_date": "2020-01-01", "end_date": None, "employment_type": "Casual"}
])
classes = pd.DataFrame([
    {"employee_id": "E1", "effective_from": "2020-01-01", "classification_code": "SACS-L2-P3"}
])
empty_holidays = pd.DataFrame(columns=["state", "holiday_date", "holiday_name", "holiday_location_key"])
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Casual Saturday example
# MAGIC
# MAGIC Confirms the expected amount for a four-hour Saturday shift at the synthetic classification.
# COMMAND ----------
sat = pd.DataFrame([
    {"timesheet_id": "SAT", "employee_id": "E1", "start_datetime": "2026-08-08 18:00", "end_datetime": "2026-08-08 22:00", "break_units": 0, "work_group": "DISABILITY_SERVICES", "location_state": "WA", "pay_period_start": "2026-08-03", "pay_period_end": "2026-08-16"}
])
detail = calculate_entitlements(employees, history, classes, sat, empty_holidays, lib)
ok("casual Saturday calculation", float(detail.iloc[0].expected_amount) == 269.52, detail.iloc[0].to_dict())
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Sleepover treatment
# MAGIC
# MAGIC Confirms that the sleepover span is represented as sleepover evidence rather than ordinary worked hours. Active sleepover work is represented separately when it occurs.
# COMMAND ----------
sleep = pd.DataFrame([
    {"timesheet_id": "SO", "employee_id": "E1", "start_datetime": "2026-08-03 22:00", "end_datetime": "2026-08-04 06:00", "break_units": 0, "work_group": "DISABILITY_SERVICES", "location_state": "WA", "pay_period_start": "2026-08-03", "pay_period_end": "2026-08-16", "is_sleepover": True}
])
detail = calculate_entitlements(employees, history, classes, sleep, empty_holidays, lib)
ok("sleepover is not ordinary worked hours", float(detail.iloc[0].worked_hours) == 0 and float(detail.iloc[0].sleepover_span_hours) == 8, detail.iloc[0].to_dict())
ok("sleepover allowance evidence", "SLEEPOVER_ALLOWANCE" in detail.iloc[0].calculation_evidence, detail.iloc[0].calculation_evidence)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Local public holiday matching
# MAGIC
# MAGIC Confirms that a local holiday applies only to the matching `holiday_location_key`.
# COMMAND ----------
local_ts = pd.DataFrame([
    {"timesheet_id": "LOCAL", "employee_id": "E1", "start_datetime": "2026-09-28 09:00", "end_datetime": "2026-09-28 13:00", "break_units": 0, "work_group": "DISABILITY_SERVICES", "location_state": "WA", "holiday_location_key": "KUNUNURRA", "pay_period_start": "2026-09-21", "pay_period_end": "2026-10-04"},
    {"timesheet_id": "OTHER", "employee_id": "E1", "start_datetime": "2026-09-28 14:00", "end_datetime": "2026-09-28 18:00", "break_units": 0, "work_group": "DISABILITY_SERVICES", "location_state": "WA", "holiday_location_key": "PERTH", "pay_period_start": "2026-09-21", "pay_period_end": "2026-10-04"},
])
local_holidays = pd.DataFrame([
    {"state": "WA", "holiday_date": "2026-09-28", "holiday_name": "Local Holiday", "holiday_location_key": "KUNUNURRA", "holiday_scope": "LOCAL", "source": "self_test"}
])
detail = calculate_entitlements(employees, history, classes, local_ts, local_holidays, lib)
evidence = dict(zip(detail.timesheet_id, detail.calculation_evidence))
ok("local holiday applies to matching location", "PUBLIC_HOLIDAY" in evidence["LOCAL"])
ok("local holiday does not leak statewide", "PUBLIC_HOLIDAY" not in evidence["OTHER"])
# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Broken-shift grouping and allowance
# MAGIC
# MAGIC Confirms that separated work periods can be grouped as the same eligible broken shift and produce the expected allowance evidence.
# COMMAND ----------
broken = pd.DataFrame([
    {"timesheet_id": "B1", "employee_id": "E1", "start_datetime": "2026-08-03 07:00", "end_datetime": "2026-08-03 09:00", "break_units": 0, "work_group": "DISABILITY_SERVICES", "location_state": "WA", "pay_period_start": "2026-08-03", "pay_period_end": "2026-08-16"},
    {"timesheet_id": "B2", "employee_id": "E1", "start_datetime": "2026-08-03 16:00", "end_datetime": "2026-08-03 19:00", "break_units": 0, "work_group": "DISABILITY_SERVICES", "location_state": "WA", "pay_period_start": "2026-08-03", "pay_period_end": "2026-08-16"},
])
broken = group_broken_shifts(broken)
detail = calculate_entitlements(employees, history, classes, broken, empty_holidays, lib)
detail = apply_broken_shift_rules(detail, broken, lib)
ok("broken shift grouped", broken.broken_shift_group_id.notna().all())
ok("broken shift allowance applied", any("BROKEN_SHIFT_ALLOWANCE" in x for x in detail.calculation_evidence))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. Weekly threshold overtime allocation
# MAGIC
# MAGIC Confirms that hours above the synthetic weekly threshold are allocated and repriced by the period-overtime stage.
# COMMAND ----------
week = []
for day in range(3, 8):
    week.append({"timesheet_id": f"W{day}", "employee_id": "E1", "start_datetime": f"2026-08-{day:02d} 08:00", "end_datetime": f"2026-08-{day:02d} 16:00", "break_units": 0, "work_group": "DISABILITY_SERVICES", "location_state": "WA", "pay_period_start": "2026-08-03", "pay_period_end": "2026-08-09"})

detail = calculate_entitlements(employees, history, classes, pd.DataFrame(week), empty_holidays, lib)
detail = allocate_period_overtime(detail, empty_holidays, lib)
ok("weekly threshold overtime allocation", any("PERIOD_OVERTIME_REPRICE" in x for x in detail.calculation_evidence))

print(f"\nAuditHero self-test complete: {len(passed)} checks passed.")
print("NEXT: validate source data and mapping, then run one known payroll period.")
