# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Preview and Prepare Uploaded Files
# MAGIC
# MAGIC **Purpose:** inspect ordinary payroll, timesheet and employee/rate CSV/XLSX files, show AuditHero's interpretation, and prepare canonical inputs without starting an audit.
# MAGIC
# MAGIC Review the interpretation and warnings before running the prepared-file audit. If a file role or field is wrong, use **AuditHero - Build Source Mapping Workbook (Advanced)** to create a correction/context workbook.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1"
# COMMAND ----------
from pathlib import Path
import json
import shutil
import tempfile
import pandas as pd

exec(open(str(Path.cwd() / "_common.py")).read())
from schads_audit.auto_intake import build_auto_canonical
from schads_audit.dates import iso_date
from schads_audit.file_source import prune_frames_to_window

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("source_root", "")
dbutils.widgets.text("output_root", "")
dbutils.widgets.text("start_date", "")
dbutils.widgets.text("end_date", "")

catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"
source_root = dbutils.widgets.get("source_root").strip() or f"/Volumes/{catalog}/bronze/landing/import/raw"
output_root = dbutils.widgets.get("output_root").strip() or f"/Volumes/{catalog}/bronze/landing/auto_input"
start_override = dbutils.widgets.get("start_date").strip()
end_override = dbutils.widgets.get("end_date").strip()

if bool(start_override) != bool(end_override):
    raise ValueError("Supply both start_date and end_date to preview a specific audit window, or leave both blank for automatic detection.")

print(f"Source folder: {source_root}")
print(f"Prepared canonical folder: {output_root}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Detect and preview the supplied files
# COMMAND ----------
result = build_auto_canonical(source_root)
frames = result["frames"]
metadata = result["metadata"]
start_date = start_override or metadata.get("start_date")
end_date = end_override or metadata.get("end_date")
if not start_date or not end_date:
    raise ValueError("AuditHero could not determine the audit date range from the supplied shifts.")

start_iso = iso_date(start_date)
end_iso = iso_date(end_date)
if pd.Timestamp(end_iso) < pd.Timestamp(start_iso):
    raise ValueError(f"end_date must be on or after start_date: {start_date} to {end_date}")

# Reduce prepared evidence to the requested audit window before publishing it.
# This keeps the reviewed-file audit fast even when the original exports contain
# several years of historical data.
frames = prune_frames_to_window(frames, start_iso, end_iso)
if frames.get("timesheets") is None or frames["timesheets"].empty:
    raise ValueError(f"No timesheets fall inside the requested audit window: {start_iso} to {end_iso}")

interpretation = pd.DataFrame(metadata.get("interpretation") or [])
if not interpretation.empty:
    display(interpretation)
for warning in metadata.get("warnings", []) or []:
    print(f"REVIEW: {warning}")

print(f"Resolved audit window: {start_iso} to {end_iso}")
print("Prepared row counts for this window:")
for name, frame in frames.items():
    if frame is not None and not frame.empty:
        print(f"  {name}: {len(frame):,}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Publish prepared canonical files and interpretation evidence
# MAGIC
# MAGIC This step does not calculate entitlements. The prepared folder is isolated from previously mapped inputs so stale files cannot affect a later audit.
# COMMAND ----------
dbutils.fs.rm(output_root, True)
dbutils.fs.mkdirs(output_root)
stage = Path(tempfile.mkdtemp(prefix="audithero-auto-intake-"))
try:
    for name, frame in frames.items():
        if frame is None or frame.empty:
            continue
        local = stage / f"{name}.csv"
        frame.to_csv(local, index=False)
        shutil.copyfile(local, Path(output_root) / local.name)
    if not interpretation.empty:
        preview_file = stage / "auto_intake_preview.csv"
        interpretation.assign(
            detected_roles=interpretation["detected_roles"].map(lambda x: json.dumps(x, default=str)),
            mapped_fields=interpretation["mapped_fields"].map(lambda x: json.dumps(x, default=str)),
        ).to_csv(preview_file, index=False)
        shutil.copyfile(preview_file, Path(output_root) / preview_file.name)
    manifest = {
        **metadata,
        "audit_start_date": start_iso,
        "audit_end_date": end_iso,
        "prepared_window_start": start_iso,
        "prepared_window_end": end_iso,
        "mode": "AUTO_INTAKE_PREVIEW",
    }
    manifest_path = stage / "auto_intake_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    shutil.copyfile(manifest_path, Path(output_root) / manifest_path.name)
finally:
    shutil.rmtree(stage, ignore_errors=True)

dbutils.jobs.taskValues.set(key="start_date", value=start_iso)
dbutils.jobs.taskValues.set(key="end_date", value=end_iso)
dbutils.jobs.taskValues.set(key="output_root", value=output_root)

print(f"Employees identified: {metadata['employees']}")
print(f"Timesheet rows prepared for audit window: {len(frames['timesheets']):,}")
print(f"Payroll earning rows prepared for audit window: {len(frames.get('payroll_earnings', pd.DataFrame())):,}")
print(f"Audit window: {start_iso} to {end_iso}")
print("Preview preparation complete. Review the interpretation before starting the prepared-file audit.")
print("If a role or field is wrong, use the Advanced Mapping workbook to correct it and run the mapped-file workflow instead.")
