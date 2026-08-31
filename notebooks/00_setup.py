# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Setup
# MAGIC
# MAGIC **Purpose:** prepare the Databricks catalog for AuditHero. Run this after first deployment and again after an approved upgrade.
# MAGIC
# MAGIC This notebook:
# MAGIC 1. validates the effective-dated SCHADS rule library;
# MAGIC 2. creates the Unity Catalog schemas used by AuditHero;
# MAGIC 3. loads reference rates/conditions/allowances;
# MAGIC 4. creates operational and audit output Delta tables; and
# MAGIC 5. creates the latest-successful-run views used by jobs and AI/BI.
# MAGIC
# MAGIC It does **not** read employee payroll data and does not calculate an audit.
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Load the shared AuditHero package and choose the catalog
# MAGIC
# MAGIC The `catalog` parameter defaults to `schads_payroll`. If your deployment uses another catalog, the job passes it here through a Databricks widget.
# COMMAND ----------
exec(open(str(Path.cwd() / "_common.py")).read())

from schads_audit.rules import RuleLibrary
from schads_audit.databricks_io import (
    create_catalog_objects,
    overwrite_rule_tables,
    create_views,
)

dbutils.widgets.text("catalog", "schads_payroll")
catalog = dbutils.widgets.get("catalog")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Validate the SCHADS rule library
# MAGIC
# MAGIC `RuleLibrary.validate()` checks that the manifest and effective-dated rate, condition and allowance packs are internally usable. Setup stops if the rule library is invalid rather than creating a workspace with incomplete rules.
# COMMAND ----------
lib = RuleLibrary(ROOT / "rules/MA000100")
errors = lib.validate()
if errors:
    raise ValueError("\n".join(errors))

print("SCHADS rule library validated")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Create schemas and load reference tables
# MAGIC
# MAGIC AuditHero uses separate schemas for source/normalized data, rule references, audit results and operational run status. `overwrite_rule_tables` refreshes only the reference tables from the source-controlled rule packs; it does not overwrite payroll results.
# COMMAND ----------
create_catalog_objects(spark, catalog)
overwrite_rule_tables(spark, lib, catalog)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Ensure operational and result tables exist
# MAGIC
# MAGIC `CREATE TABLE IF NOT EXISTS` makes this step safe to rerun. These tables store audit run history, readiness findings, shift-level entitlement evidence, event/TOIL adjustments and pay-period reconciliation.
# COMMAND ----------
spark.sql(
    f"CREATE TABLE IF NOT EXISTS `{catalog}`.`ops`.`audit_runs` ("
    "audit_run_id STRING,run_type STRING,audit_window_start STRING,audit_window_end STRING,"
    "started_at TIMESTAMP,finished_at TIMESTAMP,status STRING,actual_pay_source STRING,"
    "employees BIGINT,timesheets BIGINT,underpaid_periods BIGINT,overpaid_periods BIGINT,"
    "review_periods BIGINT,message STRING) USING DELTA"
)
spark.sql(
    f"CREATE TABLE IF NOT EXISTS `{catalog}`.`ops`.`readiness_findings` ("
    "finding_type STRING,source_key STRING,source_label STRING,status STRING,detail STRING,"
    "checked_at TIMESTAMP) USING DELTA"
)
spark.sql(
    f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`audit_detail` (
    timesheet_id STRING,employee_id STRING,employee_name STRING,employment_type STRING,
    classification_code STRING,work_group STRING,state STRING,holiday_location_key STRING,
    pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,award_reference_date TIMESTAMP,
    shift_start TIMESTAMP,shift_end TIMESTAMP,worked_hours DOUBLE,sleepover_span_hours DOUBLE,
    base_hourly_rate DOUBLE,expected_amount DOUBLE,entitlement_status STRING,review_flags STRING,
    calculation_evidence STRING,industrial_instrument_type STRING,industrial_instrument_name STRING,
    instrument_reference STRING,instrument_coverage_status STRING,part_time_pattern_status STRING,
    part_time_pattern_reference STRING,part_time_variation_reference STRING,audit_run_id STRING,
    audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP
    ) USING DELTA"""
)
spark.sql(
    f"CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`audit_event_adjustments` ("
    "event_id STRING,employee_id STRING,employee_name STRING,event_type STRING,"
    "pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,expected_adjustment DOUBLE,"
    "event_status STRING,review_flags STRING,calculation_evidence STRING,audit_run_id STRING,"
    "audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP) USING DELTA"
)
spark.sql(
    f"CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`toil_findings` ("
    "toil_agreement_id STRING,employee_id STRING,employee_name STRING,overtime_datetime TIMESTAMP,"
    "overtime_hours DOUBLE,time_off_hours DOUBLE,remaining_hours DOUBLE,deadline TIMESTAMP,"
    "payment_date TIMESTAMP,payment_reason STRING,expected_adjustment DOUBLE,status STRING,"
    "review_flags STRING,calculation_evidence STRING,pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,"
    "audit_run_id STRING,audit_window_start STRING,audit_window_end STRING,run_type STRING,"
    "run_finished_at TIMESTAMP) USING DELTA"
)
spark.sql(
    f"CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`pay_period_reconciliation` ("
    "employee_id STRING,employee_name STRING,pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,"
    "expected_amount DOUBLE,shift_count BIGINT,entitlement_review_count BIGINT,"
    "actual_auditable_amount DOUBLE,unmapped_pay_categories STRING,"
    "variance_actual_minus_expected DOUBLE,status STRING,audit_run_id STRING,"
    "audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP) USING DELTA"
)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Create operator-facing views
# MAGIC
# MAGIC These views select the latest successful audit data for dashboards and review. A failed rerun therefore does not automatically replace the last successful result.
# COMMAND ----------
create_views(spark, catalog)

print("AuditHero Databricks setup complete")
print(f"Raw import folder:       /Volumes/{catalog}/bronze/landing/import/raw")
print(f"Canonical input folder:  /Volumes/{catalog}/bronze/landing/input")
print("NEXT: run 'AuditHero - Self Test'.")
