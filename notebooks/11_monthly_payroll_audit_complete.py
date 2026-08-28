# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Complete Monthly Payroll Audit
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd() / "_common.py")).read())
from schads_audit.config import AuditConfig
from schads_audit.rules import RuleLibrary
from schads_audit.dates import recent_window, previous_calendar_month
from schads_audit.databricks_pipeline_v2 import run_databricks_audit_v2
from schads_audit.databricks_io import create_views

dbutils.widgets.text("catalog","schads_payroll")
dbutils.widgets.text("secret_scope","audithero")
dbutils.widgets.dropdown("period_mode","RECENT_45_DAYS",["RECENT_45_DAYS","PREVIOUS_CALENDAR_MONTH","EXPLICIT"])
dbutils.widgets.text("start_date","")
dbutils.widgets.text("end_date","")
dbutils.widgets.dropdown("actual_pay_source","PAYROLL_API",["PAYROLL_API","NONE"])

cfg=AuditConfig(catalog=dbutils.widgets.get("catalog"),secret_scope=dbutils.widgets.get("secret_scope"),actual_pay_source=dbutils.widgets.get("actual_pay_source"))
mode=dbutils.widgets.get("period_mode")
if mode=="PREVIOUS_CALENDAR_MONTH":
    start_date,end_date=previous_calendar_month(cfg.timezone)
elif mode=="EXPLICIT":
    start_date,end_date=dbutils.widgets.get("start_date"),dbutils.widgets.get("end_date")
    if not start_date or not end_date: raise ValueError("EXPLICIT mode requires dates")
else:
    start_date,end_date=recent_window(45,cfg.timezone)

lib=RuleLibrary(ROOT/"rules/MA000100")
result=run_databricks_audit_v2(spark,dbutils,cfg,lib,start_date,end_date,ROOT/"config",run_type="MONTHLY",actual_pay_source=cfg.actual_pay_source)
create_views(spark,cfg.catalog)
print(f"Complete monthly audit: {result['run_id']} ({start_date} to {end_date})")
if not result['reconciliation'].empty:
    print(result['reconciliation']['status'].value_counts(dropna=False).to_string())
