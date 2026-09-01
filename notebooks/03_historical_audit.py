# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Historical SCHADS Audit (Optional API)
# MAGIC
# MAGIC **Purpose:** run an Employment Hero API-sourced payroll audit for a selected historical date range.
# MAGIC
# MAGIC The workflow performs extraction, normalization, evidence checks, effective-dated SCHADS calculation, reconciliation, and persistence. Results are stored in the AuditHero Delta tables and exposed through the governed reporting layer.
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

from schads_audit.config import AuditConfig
from schads_audit.rules import RuleLibrary
from schads_audit.databricks_pipeline_v2 import run_databricks_audit_v2
from schads_audit.databricks_io import create_views
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Set the audit parameters
# MAGIC
# MAGIC `start_date` and `end_date` define the extraction and audit window. `PAYROLL_API` reconciles expected pay with Employment Hero Payroll earnings; `NONE` calculates expected entitlements without actual-pay reconciliation.
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
# MAGIC ## 2. Run the historical audit
# MAGIC
# MAGIC The shared pipeline extracts employee, pay, employment-history, timesheet, roster, and optional payroll-earnings data; applies configured mappings and evidence controls; calculates expected entitlements; persists Silver and Gold records; and records the audit run.
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
# MAGIC ## 3. Refresh reporting views and display the audit summary
# COMMAND ----------
create_views(spark, cfg.catalog)
print(f"Historical audit complete: {result['run_id']}")
if not result["reconciliation"].empty:
    print(result["reconciliation"]["status"].value_counts(dropna=False).to_string())
    display(result["reconciliation"].sort_values(["status", "employee_name"]).head(500))
print("Recommended next step: review the AuditHero - SCHADS Payroll Compliance dashboard, Genie analysis, and detailed audit evidence.")
