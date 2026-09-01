# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Setup
# MAGIC
# MAGIC **Purpose:** prepare the Databricks catalog for AuditHero. Run this after first deployment and again after an approved upgrade.
# MAGIC
# MAGIC This notebook validates SCHADS rules, creates Unity Catalog storage/tables/views,
# MAGIC creates the governed semantic metric views and provisions the AuditHero Genie Agent.
# MAGIC It does **not** read employee payroll data and does not calculate an audit.
# COMMAND ----------
# MAGIC %pip install "holidays>=0.75" "requests>=2.32" "pandas>=2.0" "databricks-sdk>=0.20"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

from databricks.sdk import WorkspaceClient
from schads_audit.rules import RuleLibrary
from schads_audit.databricks_io import (
    create_catalog_objects,
    overwrite_rule_tables,
    create_views,
    create_metric_views,
)

dbutils.widgets.text("catalog", "schads_payroll")
catalog = dbutils.widgets.get("catalog")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Validate the effective-dated SCHADS rule library
# COMMAND ----------
lib = RuleLibrary(ROOT / "rules/MA000100")
errors = lib.validate()
if errors:
    raise ValueError("\n".join(errors))
print("SCHADS rule library validated")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Create Unity Catalog structures and load reference rules
# COMMAND ----------
create_catalog_objects(spark, catalog)
overwrite_rule_tables(spark, lib, catalog)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Ensure operational and Gold result tables exist
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
# MAGIC ## 4. Create latest-successful views and governed Unity Catalog metric views
# COMMAND ----------
create_views(spark, catalog)
create_metric_views(spark, catalog)
print(f"Created semantic metric views in {catalog}.semantic")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Create or update the AuditHero Genie Agent
# MAGIC
# MAGIC Setup selects the same AuditHero SQL warehouse when present, otherwise another
# MAGIC available SQL warehouse. The managed child notebook runs only after the trusted
# MAGIC Gold views and metric views exist, avoiding broken Genie deployments on a clean install.
# COMMAND ----------
w = WorkspaceClient()
payload = w.api_client.do("GET", "/api/2.0/sql/warehouses") or {}
warehouses = payload.get("warehouses", []) or []
preferred = next((x for x in warehouses if x.get("name") == "AuditHero SQL Warehouse"), None)
selected = preferred or next((x for x in warehouses if x.get("state") == "RUNNING"), None) or (warehouses[0] if warehouses else None)
if selected is None:
    raise RuntimeError("AuditHero Setup requires a SQL warehouse for AI/BI and Genie. Create or select a SQL warehouse and rerun Setup.")
warehouse_id = selected["id"]

genie_space_id = dbutils.notebook.run(
    "./00c_setup_genie",
    600,
    {
        "catalog": catalog,
        "sql_warehouse_id": warehouse_id,
        "parent_path": "/Workspace/Shared/AuditHero",
    },
)

print("AuditHero Databricks setup complete")
print(f"Raw import folder:       /Volumes/{catalog}/bronze/landing/import/raw")
print(f"Canonical input folder:  /Volumes/{catalog}/bronze/landing/input")
print(f"Payroll metric view:     {catalog}.semantic.payroll_compliance")
print(f"Audit detail metric view:{catalog}.semantic.audit_detail")
print(f"Genie Agent ID:          {genie_space_id}")
print("NEXT: upload CSV/XLSX files to the raw import folder and run 'AuditHero - Build Source Mapping Workbook', or configure Employment Hero API credentials.")
