# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Monthly Payroll Audit (Optional API)
# MAGIC
# MAGIC **Purpose:** run the recurring Employment Hero API audit over a rolling lookback window.
# MAGIC
# MAGIC The Databricks Job schedule is paused by default and should be enabled only after a representative payroll period has been validated. File-based audits use the uploaded-file Jobs instead.
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

from schads_audit.config import AuditConfig
from schads_audit.rules import RuleLibrary
from schads_audit.dates import recent_window
from schads_audit.databricks_pipeline_v2 import run_databricks_audit_v2
from schads_audit.databricks_io import create_views
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Configure the rolling audit window
# MAGIC
# MAGIC `lookback_days` defines the rolling date window used for extraction and audit processing. The date helper resolves the window in the configured AuditHero timezone.
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("secret_scope", "audithero")
dbutils.widgets.text("lookback_days", "45")
dbutils.widgets.dropdown("actual_pay_source", "PAYROLL_API", ["PAYROLL_API", "NONE"])

cfg = AuditConfig(
    catalog=dbutils.widgets.get("catalog"),
    secret_scope=dbutils.widgets.get("secret_scope"),
    actual_pay_source=dbutils.widgets.get("actual_pay_source"),
)
start_date, end_date = recent_window(int(dbutils.widgets.get("lookback_days")), cfg.timezone)
lib = RuleLibrary(ROOT / "rules/MA000100")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run the recurring API audit
# MAGIC
# MAGIC The shared AuditHero pipeline performs extraction, normalization, evidence controls, effective-dated entitlement calculation, reconciliation and persistence for the resolved date window.
# COMMAND ----------
result = run_databricks_audit_v2(
    spark,
    dbutils,
    cfg,
    lib,
    start_date,
    end_date,
    ROOT / "config",
    run_type="MONTHLY",
    actual_pay_source=cfg.actual_pay_source,
)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Refresh reporting views and display the run summary
# COMMAND ----------
create_views(spark, cfg.catalog)
print(f"Monthly audit complete: {result['run_id']} ({start_date} to {end_date})")
if not result["reconciliation"].empty:
    print(result["reconciliation"]["status"].value_counts(dropna=False).to_string())
    display(result["reconciliation"].sort_values(["status", "employee_name"]).head(500))
print("NEXT: review the AuditHero - SCHADS Payroll Compliance dashboard and the AuditHero - Payroll Compliance Genie space.")
