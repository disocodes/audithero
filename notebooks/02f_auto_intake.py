# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Auto Prepare Uploaded Files
# MAGIC
# MAGIC **Purpose:** identify ordinary timesheet and employee/pay-rate CSV/XLSX files automatically and prepare canonical AuditHero inputs without a mapping workbook.
# MAGIC
# MAGIC A usable timesheet needs an employee name or identifier plus shift start and end. Other fields are enrichment: hours, hourly rate, employment type, classification, state, work type and pay-period dates are used when present. Missing enrichment does not stop Award scenario analysis.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1"
# COMMAND ----------
from pathlib import Path
import json
import shutil
import tempfile

exec(open(str(Path.cwd() / "_common.py")).read())

from schads_audit.auto_intake import build_auto_canonical

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

print(f"Source folder: {source_root}")
print(f"Automatic canonical folder: {output_root}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Detect and normalize the supplied files
# COMMAND ----------
result = build_auto_canonical(source_root)
frames = result["frames"]
metadata = result["metadata"]
start_date = start_override or metadata.get("start_date")
end_date = end_override or metadata.get("end_date")
if not start_date or not end_date:
    raise ValueError("AuditHero could not determine the audit date range from the supplied shifts.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Publish canonical files
# MAGIC
# MAGIC The automatic input folder is isolated from manually mapped inputs so stale files from a previous workflow cannot affect this audit.
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
    manifest = {
        **metadata,
        "audit_start_date": start_date,
        "audit_end_date": end_date,
        "mode": "AUTO_INTAKE",
    }
    manifest_path = stage / "auto_intake_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copyfile(manifest_path, Path(output_root) / manifest_path.name)
finally:
    shutil.rmtree(stage, ignore_errors=True)

# Expose dates to downstream Job tasks.
dbutils.jobs.taskValues.set(key="start_date", value=start_date)
dbutils.jobs.taskValues.set(key="end_date", value=end_date)
dbutils.jobs.taskValues.set(key="output_root", value=output_root)

print(f"Employees identified: {metadata['employees']}")
print(f"Timesheet rows identified: {metadata['timesheets']}")
print(f"Audit window: {start_date} to {end_date}")
print("Automatic preparation complete. The next Job task runs the complete SCHADS audit and Award scenario calculations.")
