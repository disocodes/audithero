# Databricks notebook source
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read());from schads_audit.config import AuditConfig;from schads_audit.rules import RuleLibrary;from schads_audit.pipeline import run_databricks_audit
dbutils.widgets.text('catalog','schads_payroll');dbutils.widgets.text('secret_scope','audithero');dbutils.widgets.text('start_date','2023-07-01');dbutils.widgets.text('end_date','2026-06-30');dbutils.widgets.dropdown('actual_pay_source','PAYROLL_API',['PAYROLL_API','NONE']);cfg=AuditConfig(catalog=dbutils.widgets.get('catalog'),secret_scope=dbutils.widgets.get('secret_scope'),actual_pay_source=dbutils.widgets.get('actual_pay_source'));r=run_databricks_audit(spark,dbutils,cfg,RuleLibrary(ROOT/'rules/MA000100'),dbutils.widgets.get('start_date'),dbutils.widgets.get('end_date'),ROOT/'config','HISTORICAL',cfg.actual_pay_source);display(r['reconciliation'].head(500))
