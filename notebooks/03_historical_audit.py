# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Historical SCHADS Audit (Optional API)
# MAGIC
# MAGIC **Purpose:** run a date-range audit using Employment Hero HR/Payroll API extraction. This is optional; the uploaded-file audit uses the same calculation engine without API credentials.
# MAGIC
# MAGIC The notebook delegates ingestion/normalization and SCHADS calculation to the shared AuditHero package, then refreshes latest-successful views and shows a reconciliation summary.
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd() / "_common.py")).read())

from schads_audit.config import AuditConfig
from schads_audit.rules import RuleLibrary
from schads_audit.databricks_pipeline_v2 import run_databricks_audit_v2
from schads_audit.databricks_io import create_views
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Audit parameters
# MAGIC
# MAGIC `start_date`/`end_date` define the extraction/audit window. `PAYROLL_API` asks AuditHero to reconcile expected pay with Employment Hero Payroll earnings; `NONE` calculates expected entitlements only.
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("secret_scope", "audithero")
dbutils.widgets.text("start_date", "2023-07-01")
dbutils.widgets.text("end_date", "2026-06-30")
dbutils.widgets.dropdown("actual_pay_source", "PAYROLL_API", ["PAYROLL_API", "NONE"])

cfg = AuditConfig(
    catalog=dbutils.widgets.get("catalog"),
    secret_scope=dbutils.widgets.get("secret_scope"),
    actual_pay_source=dbutils.widgets.get("actual_pay_source"),
)
lib = RuleLibrary(ROOT / "rules/MA000100")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run the complete shared audit pipeline
# MAGIC
# MAGIC The shared pipeline pulls employee/pay/employment history, timesheets, rosters and optional payroll earnings; applies mappings; executes the same rule modules used by FILES mode; persists Silver/Gold evidence; and records the audit run. This notebook intentionally does not reimplement those formulas.
# COMMAND ----------
result = run_databricks_audit_v2(
    spark,
    dbutils,
    cfg,
    lib,
    dbutils.widgets.get("start_date"),
    dbutils.widgets.get("end_date"),
    ROOT / "config",
    run_type="HISTORICAL",
    actual_pay_source=cfg.actual_pay_source,
)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Refresh operator views and show the result summary
# MAGIC
# MAGIC The summary is useful for immediate review; the detailed evidence remains in the Gold tables and AI/BI dashboard.
# COMMAND ----------
create_views(spark, cfg.catalog)
print(f"Historical audit complete: {result['run_id']}")
if not result["reconciliation"].empty:
    print(result["reconciliation"]["status"].value_counts(dropna=False).to_string())
    display(result["reconciliation"].sort_values(["status", "employee_name"]).head(500))
