# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Audit Uploaded CSV / Excel
# MAGIC
# MAGIC **Purpose:** run a file-based AuditHero payroll audit from canonical CSV files or `audithero_input.xlsx`.
# MAGIC
# MAGIC The standard uploaded-file Job runs File Readiness before invoking this notebook. The audit calculates expected entitlements, evaluates rest-between-work requirements, applies supported event and TOIL controls, reconciles actual payroll when sufficient earning-line evidence is available, stores normalized evidence and audit results, and refreshes the latest-successful reporting views.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1" "holidays>=0.75"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

from datetime import datetime, timezone
import uuid
import pandas as pd

from schads_audit.rules import RuleLibrary
from schads_audit.manual_audit import run_manual_audit
from schads_audit.databricks_io import write_df, create_views
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Set the input folder and audit dates
# MAGIC
# MAGIC If `input_root` is blank, AuditHero reads `/Volumes/<catalog>/bronze/landing/input`. The start and end dates define the timesheet evidence included in this audit run.
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("input_root", "")
dbutils.widgets.text("start_date", "2023-07-01")
dbutils.widgets.text("end_date", "2026-06-30")

catalog = dbutils.widgets.get("catalog")
input_root = dbutils.widgets.get("input_root").strip() or f"/Volumes/{catalog}/bronze/landing/input"
start_date = dbutils.widgets.get("start_date")
end_date = dbutils.widgets.get("end_date")

print(f"Input folder: {input_root}")
print(f"Audit window: {start_date} to {end_date}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run the file-based audit engine
# MAGIC
# MAGIC `run_manual_audit` loads canonical evidence, assigns pay periods where supported, applies the effective-dated SCHADS modules, and returns detailed, rest-compliance, and reconciled results. Missing optional actual-pay detail does not prevent expected entitlement calculation. A new run ID is assigned to the stored evidence and results.
# COMMAND ----------
run_id = str(uuid.uuid4())
started = datetime.now(timezone.utc)
lib = RuleLibrary(ROOT / "rules/MA000100")
result = run_manual_audit(input_root, ROOT / "config", start_date, end_date, lib)
finished = datetime.now(timezone.utc)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Add audit-run metadata
# MAGIC
# MAGIC Run metadata keeps repeated audits of the same date range distinguishable and traceable.
# COMMAND ----------
for frame in (
    result["detail"],
    result["rest_break_findings"],
    result["event_adjustments"],
    result["toil_findings"],
    result["reconciliation"],
):
    if frame is not None and not frame.empty:
        frame["audit_run_id"] = run_id
        frame["audit_window_start"] = start_date
        frame["audit_window_end"] = end_date
        frame["run_type"] = "MANUAL_FILE"
        frame["run_finished_at"] = finished
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Store normalized evidence and audit results
# MAGIC
# MAGIC Silver tables retain normalized source evidence. Gold tables retain calculated entitlement, rest-between-work findings, event, TOIL, and reconciliation results. Historical runs are appended rather than overwritten.
# COMMAND ----------
for name, frame in (
    ("employees", result["employees"]),
    ("pay_details", result["pay_details"]),
    ("employment_history", result["employment_history"]),
    ("timesheets", result["timesheets"]),
    ("rostered_shifts", result["rostered_shifts"]),
    ("payroll_earnings", result["payroll_earnings"]),
    ("public_holidays", result["public_holidays"]),
):
    if frame is not None and not frame.empty:
        persisted = frame.copy()
        persisted["audit_run_id"] = run_id
        persisted["ingested_at"] = finished
        write_df(spark, persisted, f"{catalog}.silver.{name}", "append")

write_df(spark, result["detail"], f"{catalog}.gold.audit_detail", "append")
write_df(spark, result["rest_break_findings"], f"{catalog}.gold.rest_break_findings", "append")
write_df(spark, result["event_adjustments"], f"{catalog}.gold.audit_event_adjustments", "append")
write_df(spark, result["toil_findings"], f"{catalog}.gold.toil_findings", "append")
write_df(spark, result["reconciliation"], f"{catalog}.gold.pay_period_reconciliation", "append")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Record audit-run status and refresh reporting views
# MAGIC
# MAGIC `actual_pay_source` is recorded as `FILES` only when the supplied payroll earnings contain the fields and approved treatment mapping required for reliable reconciliation. Otherwise the run records `NONE` and retains the supplied payroll file as Silver evidence.
# COMMAND ----------
reconciliation = result["reconciliation"]
rest_findings = result["rest_break_findings"]
actual_source = "FILES" if result.get("actual_pay_usable", False) else "NONE"
run = pd.DataFrame([
    {
        "audit_run_id": run_id,
        "run_type": "MANUAL_FILE",
        "audit_window_start": start_date,
        "audit_window_end": end_date,
        "started_at": started,
        "finished_at": finished,
        "status": "SUCCESS",
        "actual_pay_source": actual_source,
        "employees": len(result["employees"]),
        "timesheets": len(result["timesheets"]),
        "underpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "UNDERPAID").sum()),
        "overpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "OVERPAID").sum()),
        "review_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "REQUIRES_REVIEW").sum()),
        "message": f"manual input={input_root}; rest_findings={len(rest_findings)}",
    }
])
write_df(spark, run, f"{catalog}.ops.audit_runs", "append")
create_views(spark, catalog)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Display the audit summary
# COMMAND ----------
print(f"Uploaded-file audit complete: {run_id}")
if not reconciliation.empty:
    print(reconciliation["status"].value_counts(dropna=False).to_string())
    display(reconciliation.sort_values(["status", "employee_name"]).head(200))
if rest_findings is not None and not rest_findings.empty:
    print("\nRest-between-work findings:")
    print(rest_findings["status"].value_counts(dropna=False).to_string())
    display(rest_findings.sort_values(["status", "employee_name", "next_shift_start"]).head(200))
print("Recommended next step: review the AuditHero - SCHADS Payroll Compliance dashboard, Genie analysis, and detailed audit evidence.")
