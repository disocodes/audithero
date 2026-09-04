# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Audit Prepared or Canonical CSV / Excel
# MAGIC
# MAGIC **Purpose:** run a file-based AuditHero payroll audit from reviewed canonical CSV files or `audithero_input.xlsx`.
# MAGIC
# MAGIC For automatically prepared uploads, review `auto_intake_preview.csv` first. If the interpretation is correct, run this notebook/job against the prepared folder. If correction is required, use the Advanced Mapping workflow instead.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1" "holidays>=0.75"
# COMMAND ----------
from pathlib import Path
import json
from time import perf_counter

exec(open(str(Path.cwd() / "_common.py")).read())

from datetime import datetime, timezone
import uuid
import pandas as pd

from schads_audit.dates import iso_date
from schads_audit.rules import RuleLibrary
from schads_audit.manual_audit import run_manual_audit
from schads_audit.databricks_io import write_df, create_views
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Set the input folder and audit dates
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("input_root", "")
dbutils.widgets.text("start_date", "")
dbutils.widgets.text("end_date", "")
dbutils.widgets.text("run_type", "MANUAL_FILE")

catalog = dbutils.widgets.get("catalog")
input_root = dbutils.widgets.get("input_root").strip() or f"/Volumes/{catalog}/bronze/landing/input"
start_date = dbutils.widgets.get("start_date").strip()
end_date = dbutils.widgets.get("end_date").strip()
run_type = dbutils.widgets.get("run_type").strip() or "MANUAL_FILE"

if bool(start_date) != bool(end_date):
    raise ValueError(
        "Supply both start_date and end_date, or leave both blank to use the date range from auto_intake_manifest.json. "
        f"Received start_date={start_date!r}, end_date={end_date!r}."
    )

manifest_path = Path(input_root) / "auto_intake_manifest.json"
window_source = "JOB_PARAMETERS"
if not start_date and not end_date:
    if not manifest_path.exists():
        raise ValueError("Audit dates were not supplied and auto_intake_manifest.json was not found in the prepared input folder.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    start_date = str(manifest.get("audit_start_date") or manifest.get("start_date") or "").strip()
    end_date = str(manifest.get("audit_end_date") or manifest.get("end_date") or "").strip()
    window_source = "AUTO_INTAKE_MANIFEST"
if not start_date or not end_date:
    raise ValueError("Audit dates could not be determined. Supply both start_date/end_date or rerun the preview job with a valid date window.")

start_iso = iso_date(start_date)
end_iso = iso_date(end_date)
if pd.Timestamp(end_iso) < pd.Timestamp(start_iso):
    raise ValueError(f"end_date must be on or after start_date: {start_date} to {end_date}")

print(f"Input folder: {input_root}")
print(f"Audit window source: {window_source}")
print(f"Audit window entered/detected: {start_date} to {end_date}")
print(f"Audit window resolved: {start_iso} to {end_iso}")
print("Audit scope: full AuditHero calculation and Award scenario analysis for the requested date window")
print(f"Run type: {run_type}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run the file-based audit engine
# COMMAND ----------
run_id = str(uuid.uuid4())
started = datetime.now(timezone.utc)
lib = RuleLibrary(ROOT / "rules/MA000100")

classification_catalog = {}
for pack in lib.rate_packs:
    family = str(pack.get("classification_family") or "OTHER")
    for rate in pack.get("rates", []):
        code = str(rate.get("classification_code") or "").strip()
        if code:
            classification_catalog[code] = family
scenario_passes = 0
for family in classification_catalog.values():
    work_group_count = 2 if family == "HOME_CARE_DISABILITY" else 1
    scenario_passes += work_group_count * 3
print(f"Full Award scenario passes configured: {scenario_passes}")

engine_started = perf_counter()
result = run_manual_audit(
    input_root,
    ROOT / "config",
    start_iso,
    end_iso,
    lib,
    generate_award_scenarios=True,
)
engine_seconds = perf_counter() - engine_started
finished = datetime.now(timezone.utc)

print(f"Audit calculation phase completed in {engine_seconds:.1f}s")
print("Rows retained for requested audit window:")
for name in ("timesheets", "rostered_shifts", "payroll_earnings", "pay_details", "employment_history"):
    frame = result.get(name)
    print(f"  {name}: {0 if frame is None else len(frame):,}")
print("Calculated output sizes:")
for name in ("detail", "reconciliation", "award_scenario_detail", "award_criteria_detail", "award_scenario_rest_findings"):
    frame = result.get(name)
    print(f"  {name}: {0 if frame is None else len(frame):,}")
# COMMAND ----------
for frame in (
    result["detail"], result["rest_break_findings"], result["event_adjustments"],
    result["toil_findings"], result["reconciliation"], result["award_scenario_detail"],
    result["award_criteria_detail"], result["award_scenario_rest_findings"],
):
    if frame is not None and not frame.empty:
        frame["audit_run_id"] = run_id
        frame["audit_window_start"] = start_iso
        frame["audit_window_end"] = end_iso
        frame["run_type"] = run_type
        frame["run_finished_at"] = finished
# COMMAND ----------
persist_started = perf_counter()
print("Persisting filtered source evidence and calculated results...")
for name, frame in (
    ("employees", result["employees"]), ("pay_details", result["pay_details"]),
    ("employment_history", result["employment_history"]), ("timesheets", result["timesheets"]),
    ("rostered_shifts", result["rostered_shifts"]), ("payroll_earnings", result["payroll_earnings"]),
    ("public_holidays", result["public_holidays"]),
):
    if frame is not None and not frame.empty:
        persisted = frame.copy(); persisted["audit_run_id"] = run_id; persisted["ingested_at"] = finished
        write_df(spark, persisted, f"{catalog}.silver.{name}", "append")

write_df(spark, result["detail"], f"{catalog}.gold.audit_detail", "append")
write_df(spark, result["rest_break_findings"], f"{catalog}.gold.rest_break_findings", "append")
write_df(spark, result["event_adjustments"], f"{catalog}.gold.audit_event_adjustments", "append")
write_df(spark, result["toil_findings"], f"{catalog}.gold.toil_findings", "append")
write_df(spark, result["reconciliation"], f"{catalog}.gold.pay_period_reconciliation", "append")
write_df(spark, result["award_scenario_detail"], f"{catalog}.gold.award_scenario_detail", "append")
write_df(spark, result["award_criteria_detail"], f"{catalog}.gold.award_criteria_detail", "append")
write_df(spark, result["award_scenario_rest_findings"], f"{catalog}.gold.award_scenario_rest_findings", "append")
persist_seconds = perf_counter() - persist_started
print(f"Data persistence phase completed in {persist_seconds:.1f}s")
# COMMAND ----------
reconciliation = result["reconciliation"]
rest_findings = result["rest_break_findings"]
scenario_detail = result["award_scenario_detail"]
actual_source = "FILES" if result.get("actual_pay_usable", False) else "NONE"
run = pd.DataFrame([{
    "audit_run_id": run_id, "run_type": run_type, "audit_window_start": start_iso,
    "audit_window_end": end_iso, "started_at": started, "finished_at": finished,
    "status": "SUCCESS", "actual_pay_source": actual_source,
    "employees": len(result["employees"]), "timesheets": len(result["timesheets"]),
    "underpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "UNDERPAID").sum()),
    "overpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "OVERPAID").sum()),
    "review_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "REQUIRES_REVIEW").sum()),
    "message": (
        f"input={input_root}; window_source={window_source}; rest_findings={len(rest_findings)}; "
        f"award_scenarios={len(scenario_detail)}; scenario_passes={scenario_passes}; "
        f"engine_seconds={engine_seconds:.1f}; persist_seconds={persist_seconds:.1f}"
    ),
}])
write_df(spark, run, f"{catalog}.ops.audit_runs", "append")
create_views(spark, catalog)
# COMMAND ----------
total_seconds = (datetime.now(timezone.utc) - started).total_seconds()
print(f"Uploaded-file audit complete: {run_id}")
print(f"Performance summary: calculation={engine_seconds:.1f}s; persistence={persist_seconds:.1f}s; total={total_seconds:.1f}s")
if not reconciliation.empty:
    print(reconciliation["status"].value_counts(dropna=False).to_string())
    display(reconciliation.sort_values(["status", "employee_name"]).head(200))
if rest_findings is not None and not rest_findings.empty:
    print("\nRest-between-work findings:")
    print(rest_findings["status"].value_counts(dropna=False).to_string())
if scenario_detail is not None and not scenario_detail.empty:
    print(f"\nAward scenario rows available for interactive level/pay-point analysis: {len(scenario_detail):,}")
print("Recommended next step: review the AuditHero dashboard, exceptions and supporting evidence.")
