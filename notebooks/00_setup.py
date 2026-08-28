# Databricks notebook source
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read())
from schads_audit.rules import RuleLibrary
from schads_audit.databricks_io import create_catalog_objects,overwrite_rule_tables,create_views
dbutils.widgets.text('catalog','schads_payroll');catalog=dbutils.widgets.get('catalog');lib=RuleLibrary(ROOT/'rules/MA000100');errors=lib.validate()
if errors:raise ValueError('\n'.join(errors))
create_catalog_objects(spark,catalog);overwrite_rule_tables(spark,lib,catalog)
spark.sql(f"CREATE TABLE IF NOT EXISTS `{catalog}`.`ops`.`audit_runs` (audit_run_id STRING,run_type STRING,audit_window_start STRING,audit_window_end STRING,started_at TIMESTAMP,finished_at TIMESTAMP,status STRING,actual_pay_source STRING,employees BIGINT,timesheets BIGINT,underpaid_periods BIGINT,overpaid_periods BIGINT,review_periods BIGINT,message STRING) USING DELTA")
spark.sql(f"CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`audit_detail` (timesheet_id STRING,employee_id STRING,employee_name STRING,employment_type STRING,classification_code STRING,work_group STRING,state STRING,pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,award_reference_date TIMESTAMP,shift_start TIMESTAMP,shift_end TIMESTAMP,worked_hours DOUBLE,base_hourly_rate DOUBLE,expected_amount DOUBLE,entitlement_status STRING,review_flags STRING,calculation_evidence STRING,audit_run_id STRING,audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP) USING DELTA")
spark.sql(f"CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`pay_period_reconciliation` (employee_id STRING,employee_name STRING,pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,expected_amount DOUBLE,shift_count BIGINT,entitlement_review_count BIGINT,actual_auditable_amount DOUBLE,unmapped_pay_categories STRING,variance_actual_minus_expected DOUBLE,status STRING,audit_run_id STRING,audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP) USING DELTA");create_views(spark,catalog);print('AuditHero setup complete')
