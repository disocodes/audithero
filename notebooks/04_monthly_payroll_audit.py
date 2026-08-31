# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Monthly Payroll Audit (Optional API)
# MAGIC
# MAGIC **Purpose:** run the optional recurring Employment Hero API audit over a rolling lookback window. The Databricks job schedule is intentionally paused by default until a known payroll period has been validated.
# MAGIC
# MAGIC File-based organisations can operate recurring audits without this notebook by refreshing/uploading source exports and running the file conversion/audit jobs.
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
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
# MAGIC `lookback_days` is intentionally longer than many individual pay periods so recently completed periods can still be included. The helper resolves dates in the configured AuditHero timezone.
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
# MAGIC ## 2. Run the shared API audit engine
# MAGIC
# MAGIC The same rule modules used by historical and file audits are applied; this notebook only chooses a rolling date window and labels the run as MONTHLY.
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
# MAGIC ## 3. Refresh views and display a run summary
# COMMAND ----------
create_views(spark, cfg.catalog)
print(f"Monthly audit complete: {result['run_id']} ({start_date} to {end_date})")
if not result["reconciliation"].empty:
    print(result["reconciliation"]["status"].value_counts(dropna=False).to_string())
    display(result["reconciliation"].sort_values(["status", "employee_name"]).head(500))
