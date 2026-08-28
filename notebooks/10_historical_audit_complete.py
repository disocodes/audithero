# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Complete Historical Audit
# MAGIC Uses the full shared SCHADS compliance pipeline, including instrument history, part-time patterns, rest/meal controls and TOIL.
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd() / "_common.py")).read())
from schads_audit.config import AuditConfig
from schads_audit.rules import RuleLibrary
from schads_audit.databricks_pipeline_v2 import run_databricks_audit_v2
from schads_audit.databricks_io import create_views

dbutils.widgets.text("catalog","schads_payroll")
dbutils.widgets.text("secret_scope","audithero")
dbutils.widgets.text("start_date","2023-07-01")
dbutils.widgets.text("end_date","2026-06-30")
dbutils.widgets.dropdown("actual_pay_source","PAYROLL_API",["PAYROLL_API","NONE"])

cfg=AuditConfig(
    catalog=dbutils.widgets.get("catalog"),
    secret_scope=dbutils.widgets.get("secret_scope"),
    actual_pay_source=dbutils.widgets.get("actual_pay_source"),
)
lib=RuleLibrary(ROOT/"rules/MA000100")
result=run_databricks_audit_v2(
    spark,dbutils,cfg,lib,
    dbutils.widgets.get("start_date"),dbutils.widgets.get("end_date"),
    ROOT/"config",run_type="HISTORICAL",actual_pay_source=cfg.actual_pay_source,
)
create_views(spark,cfg.catalog)
print(f"Complete historical audit: {result['run_id']}")
if not result['reconciliation'].empty:
    print(result['reconciliation']['status'].value_counts(dropna=False).to_string())
    display(result['reconciliation'].sort_values(['status','employee_name']).head(200))
