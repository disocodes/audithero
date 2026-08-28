# Databricks notebook source
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read());from schads_audit.config import AuditConfig;from schads_audit.rules import RuleLibrary;from schads_audit.dates import recent_window;from schads_audit.pipeline import run_databricks_audit
dbutils.widgets.text('catalog','schads_payroll');dbutils.widgets.text('secret_scope','audithero');dbutils.widgets.text('lookback_days','45');cfg=AuditConfig(catalog=dbutils.widgets.get('catalog'),secret_scope=dbutils.widgets.get('secret_scope'));s,e=recent_window(int(dbutils.widgets.get('lookback_days')),cfg.timezone);r=run_databricks_audit(spark,dbutils,cfg,RuleLibrary(ROOT/'rules/MA000100'),s,e,ROOT/'config','MONTHLY',cfg.actual_pay_source);display(r['reconciliation'].head(500))
