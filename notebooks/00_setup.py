# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Core Environment Setup
# MAGIC
# MAGIC **Purpose:** idempotently ensure the Databricks data environment required by AuditHero.
# MAGIC
# MAGIC This core Setup task follows an **ensure / migrate / refresh-if-changed** model:
# MAGIC - persistent catalogs, schemas, volumes and Delta tables are created only when missing;
# MAGIC - existing tables are never dropped or replaced by Setup;
# MAGIC - schema migrations add only missing columns;
# MAGIC - SCHADS reference tables reload only when the packaged rule library changed;
# MAGIC - reporting / metric views refresh only when their defining source changed.
# MAGIC
# MAGIC Genie is intentionally configured by a **separate Setup job task**. A Genie/API problem must not be hidden inside this core task as a generic nested `NotebookRun` / Py4J failure.
# MAGIC
# MAGIC **Data access:** this notebook does not read employee payroll data or calculate payroll entitlements.
# COMMAND ----------
# MAGIC %pip install -q "holidays>=0.75" "requests>=2.32" "pandas>=2.0" "databricks-sdk>=0.20"
# COMMAND ----------
from pathlib import Path
from hashlib import sha256
import json

exec(open(str(Path.cwd() / "_common.py")).read())

from schads_audit.rules import RuleLibrary
from schads_audit.databricks_io import create_catalog_objects, overwrite_rule_tables, create_views, create_metric_views

dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("sql_warehouse_id", "")
catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"

raw_import_root = f"/Volumes/{catalog}/bronze/landing/import/raw"
canonical_input_root = f"/Volumes/{catalog}/bronze/landing/input"
auto_input_root = f"/Volumes/{catalog}/bronze/landing/auto_input"

SETUP_BUILD = "2026-09-08-idempotent-v2"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Setup-state helpers
# COMMAND ----------
def _qname(schema: str, name: str) -> str:
    return f"`{catalog}`.`{schema}`.`{name}`"


def _object_exists(schema: str, name: str) -> bool:
    try:
        spark.sql(f"DESCRIBE TABLE {_qname(schema, name)}").limit(1).collect()
        return True
    except Exception:
        return False


def _ensure_directory(path: str) -> None:
    try:
        dbutils.fs.ls(path)
        print(f"SKIP   directory exists: {path}")
    except Exception:
        dbutils.fs.mkdirs(path)
        print(f"CREATE directory: {path}")


def _fingerprint_tree(root: Path) -> str:
    digest = sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _fingerprint_files(paths: list[Path]) -> str:
    digest = sha256()
    for path in sorted(paths, key=lambda p: p.as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


# Catalog/schema/volume DDL in create_catalog_objects uses IF NOT EXISTS and is safe.
create_catalog_objects(spark, catalog)
print(f"ENSURE Unity Catalog base objects: {catalog}")

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS `{catalog}`.`ops`.`setup_state` (
      resource_key STRING,
      resource_version STRING,
      details STRING,
      updated_at TIMESTAMP
    ) USING DELTA
    """
)


def _state_get(resource_key: str):
    key = resource_key.replace("'", "''")
    rows = spark.sql(
        f"""
        SELECT resource_version, details
        FROM `{catalog}`.`ops`.`setup_state`
        WHERE resource_key = '{key}'
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).collect()
    return rows[0] if rows else None


def _state_put(resource_key: str, resource_version: str, details: dict | None = None) -> None:
    key = resource_key.replace("'", "''")
    version = resource_version.replace("'", "''")
    detail_text = json.dumps(details or {}, sort_keys=True, separators=(",", ":")).replace("'", "''")
    spark.sql(
        f"""
        MERGE INTO `{catalog}`.`ops`.`setup_state` t
        USING (
          SELECT
            '{key}' AS resource_key,
            '{version}' AS resource_version,
            '{detail_text}' AS details,
            current_timestamp() AS updated_at
        ) s
        ON t.resource_key = s.resource_key
        WHEN MATCHED THEN UPDATE SET
          t.resource_version = s.resource_version,
          t.details = s.details,
          t.updated_at = s.updated_at
        WHEN NOT MATCHED THEN INSERT *
        """
    )


for path in (raw_import_root, canonical_input_root, auto_input_root):
    _ensure_directory(path)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Validate and conditionally load the effective-dated SCHADS rule library
# COMMAND ----------
lib = RuleLibrary(ROOT / "rules/MA000100")
errors = lib.validate()
if errors:
    raise ValueError("\n".join(errors))
print("VALIDATE SCHADS rule library: PASS")

rules_fingerprint = _fingerprint_tree(ROOT / "rules/MA000100")
rule_tables = [
    ("ref", "rates"),
    ("ref", "conditions"),
    ("ref", "allowances"),
    ("ref", "rule_coverage"),
]
rule_state = _state_get("schads_rule_library")
rules_current = (
    rule_state is not None
    and rule_state["resource_version"] == rules_fingerprint
    and all(_object_exists(schema, name) for schema, name in rule_tables)
)

if rules_current:
    print(f"SKIP   SCHADS reference tables already current ({rules_fingerprint[:12]})")
else:
    overwrite_rule_tables(spark, lib, catalog)
    _state_put(
        "schads_rule_library",
        rules_fingerprint,
        {"tables": [f"{s}.{n}" for s, n in rule_tables]},
    )
    print(f"REFRESH SCHADS reference tables ({rules_fingerprint[:12]})")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Ensure operational and Gold result tables exist
# COMMAND ----------
TABLE_DDLS = {
    ("ops", "audit_runs"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`ops`.`audit_runs` (
      audit_run_id STRING,run_type STRING,audit_window_start STRING,audit_window_end STRING,
      started_at TIMESTAMP,finished_at TIMESTAMP,status STRING,actual_pay_source STRING,
      employees BIGINT,timesheets BIGINT,underpaid_periods BIGINT,overpaid_periods BIGINT,
      review_periods BIGINT,message STRING
    ) USING DELTA""",
    ("ops", "readiness_findings"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`ops`.`readiness_findings` (
      finding_type STRING,source_key STRING,source_label STRING,status STRING,detail STRING,checked_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "audit_detail"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`audit_detail` (
      timesheet_id STRING,employee_id STRING,employee_name STRING,employment_type STRING,
      classification_code STRING,work_group STRING,state STRING,holiday_location_key STRING,
      pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,award_reference_date TIMESTAMP,
      shift_start TIMESTAMP,shift_end TIMESTAMP,worked_hours DOUBLE,sleepover_span_hours DOUBLE,
      base_hourly_rate DOUBLE,expected_amount DOUBLE,entitlement_status STRING,review_flags STRING,
      calculation_evidence STRING,industrial_instrument_type STRING,industrial_instrument_name STRING,
      instrument_reference STRING,instrument_coverage_status STRING,part_time_pattern_status STRING,
      part_time_pattern_reference STRING,part_time_variation_reference STRING,audit_run_id STRING,
      audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "audit_event_adjustments"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`audit_event_adjustments` (
      event_id STRING,employee_id STRING,employee_name STRING,event_type STRING,
      pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,expected_adjustment DOUBLE,event_status STRING,
      review_flags STRING,calculation_evidence STRING,audit_run_id STRING,audit_window_start STRING,
      audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "toil_findings"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`toil_findings` (
      toil_agreement_id STRING,employee_id STRING,employee_name STRING,overtime_datetime TIMESTAMP,
      overtime_hours DOUBLE,time_off_hours DOUBLE,remaining_hours DOUBLE,deadline TIMESTAMP,
      payment_date TIMESTAMP,payment_reason STRING,expected_adjustment DOUBLE,status STRING,
      review_flags STRING,calculation_evidence STRING,pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,
      audit_run_id STRING,audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "rest_break_findings"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`rest_break_findings` (
      finding_id STRING,finding_type STRING,employee_id STRING,employee_name STRING,previous_timesheet_ids STRING,
      next_timesheet_ids STRING,previous_shift_end TIMESTAMP,next_shift_start TIMESTAMP,
      rule_reference_date TIMESTAMP,rule_reference_source STRING,required_rest_hours DOUBLE,
      actual_rest_hours DOUBLE,rest_shortfall_hours DOUBLE,sleepover_adjacent_exception_eligible BOOLEAN,
      sleepover_8h_agreement BOOLEAN,sleepover_blocked_rest BOOLEAN,historical_sleepover_interaction BOOLEAN,
      overtime_rest_rule_applies BOOLEAN,employer_instructed_resume BOOLEAN,release_datetime TIMESTAMP,
      double_time_repriced_hours DOUBLE,double_time_topup DOUBLE,paid_absence_rostered_hours DOUBLE,
      payment_status STRING,status STRING,clause STRING,overtime_clause STRING,evidence_reference STRING,
      notes STRING,audit_run_id STRING,audit_window_start STRING,audit_window_end STRING,run_type STRING,
      run_finished_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "pay_period_reconciliation"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`pay_period_reconciliation` (
      employee_id STRING,employee_name STRING,pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,
      expected_amount DOUBLE,shift_count BIGINT,entitlement_review_count BIGINT,actual_auditable_amount DOUBLE,
      unmapped_pay_categories STRING,variance_actual_minus_expected DOUBLE,status STRING,audit_run_id STRING,
      audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "award_scenario_detail"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`award_scenario_detail` (
      timesheet_id STRING,employee_id STRING,employee_name STRING,employment_type STRING,classification_code STRING,
      work_group STRING,state STRING,holiday_location_key STRING,pay_period_start TIMESTAMP,pay_period_end TIMESTAMP,
      award_reference_date TIMESTAMP,shift_start TIMESTAMP,shift_end TIMESTAMP,worked_hours DOUBLE,
      sleepover_span_hours DOUBLE,base_hourly_rate DOUBLE,expected_amount DOUBLE,entitlement_status STRING,
      review_flags STRING,calculation_evidence STRING,scenario_id STRING,classification_family STRING,
      scenario_classification_code STRING,scenario_classification_name STRING,scenario_level INT,scenario_pay_point INT,
      scenario_employment_type STRING,supplied_base_hourly_rate DOUBLE,source_rate_effective_from TIMESTAMP,
      source_rate_reference STRING,source_classification_code STRING,source_classification_name STRING,
      source_level_hint INT,source_employment_type STRING,base_rate_variance DOUBLE,base_rate_status STRING,
      matches_source_classification BOOLEAN,matches_source_level_hint BOOLEAN,matches_source_employment_type BOOLEAN,
      observed_shift_pay DOUBLE,shift_variance_actual_minus_expected DOUBLE,scenario_status STRING,
      audit_run_id STRING,audit_window_start STRING,audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "award_criteria_detail"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`award_criteria_detail` (
      scenario_id STRING,classification_family STRING,scenario_classification_code STRING,
      scenario_classification_name STRING,scenario_level INT,scenario_pay_point INT,scenario_employment_type STRING,
      timesheet_id STRING,employee_id STRING,employee_name STRING,shift_start TIMESTAMP,shift_end TIMESTAMP,
      worked_hours DOUBLE,entitlement_status STRING,review_flags STRING,criterion_group STRING,criterion STRING,
      clause STRING,hours DOUBLE,multiplier DOUBLE,effective_hourly_rate DOUBLE,criterion_amount DOUBLE,
      day_type STRING,shift_type STRING,detail STRING,audit_run_id STRING,audit_window_start STRING,
      audit_window_end STRING,run_type STRING,run_finished_at TIMESTAMP
    ) USING DELTA""",
    ("gold", "award_scenario_rest_findings"): f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`gold`.`award_scenario_rest_findings` (
      finding_id STRING,finding_type STRING,employee_id STRING,employee_name STRING,previous_timesheet_ids STRING,
      next_timesheet_ids STRING,previous_shift_end TIMESTAMP,next_shift_start TIMESTAMP,
      rule_reference_date TIMESTAMP,rule_reference_source STRING,required_rest_hours DOUBLE,
      actual_rest_hours DOUBLE,rest_shortfall_hours DOUBLE,sleepover_adjacent_exception_eligible BOOLEAN,
      sleepover_8h_agreement BOOLEAN,sleepover_blocked_rest BOOLEAN,historical_sleepover_interaction BOOLEAN,
      overtime_rest_rule_applies BOOLEAN,employer_instructed_resume BOOLEAN,release_datetime TIMESTAMP,
      double_time_repriced_hours DOUBLE,double_time_topup DOUBLE,paid_absence_rostered_hours DOUBLE,
      payment_status STRING,status STRING,clause STRING,overtime_clause STRING,evidence_reference STRING,notes STRING,
      scenario_id STRING,classification_family STRING,scenario_classification_code STRING,
      scenario_classification_name STRING,scenario_level INT,scenario_pay_point INT,scenario_employment_type STRING,
      criterion_group STRING,audit_run_id STRING,audit_window_start STRING,audit_window_end STRING,run_type STRING,
      run_finished_at TIMESTAMP
    ) USING DELTA""",
}

for (schema_name, table_name), ddl in TABLE_DDLS.items():
    if _object_exists(schema_name, table_name):
        print(f"SKIP   table exists: {catalog}.{schema_name}.{table_name}")
    else:
        spark.sql(ddl)
        print(f"CREATE table: {catalog}.{schema_name}.{table_name}")


def ensure_columns(table_name: str, column_specs: list[str]) -> None:
    existing = {
        row["col_name"]
        for row in spark.sql(f"DESCRIBE TABLE `{catalog}`.`gold`.`{table_name}`").collect()
        if row["col_name"] and not str(row["col_name"]).startswith("#")
    }
    missing = [spec for spec in column_specs if spec.split()[0] not in existing]
    if not missing:
        print(f"SKIP   schema current: {catalog}.gold.{table_name}")
        return
    spark.sql(f"ALTER TABLE `{catalog}`.`gold`.`{table_name}` ADD COLUMNS ({', '.join(missing)})")
    print(f"UPGRADE schema: {catalog}.gold.{table_name} (+{len(missing)} column(s))")


ensure_columns("rest_break_findings", ["rule_reference_date TIMESTAMP", "rule_reference_source STRING"])
ensure_columns("award_scenario_rest_findings", ["rule_reference_date TIMESTAMP", "rule_reference_source STRING"])
ensure_columns(
    "award_scenario_detail",
    [
        "supplied_base_hourly_rate DOUBLE",
        "source_rate_effective_from TIMESTAMP",
        "source_rate_reference STRING",
        "source_classification_code STRING",
        "source_classification_name STRING",
        "source_level_hint INT",
        "source_employment_type STRING",
        "base_rate_variance DOUBLE",
        "base_rate_status STRING",
        "matches_source_classification BOOLEAN",
        "matches_source_level_hint BOOLEAN",
        "matches_source_employment_type BOOLEAN",
        "observed_shift_pay DOUBLE",
        "shift_variance_actual_minus_expected DOUBLE",
        "scenario_status STRING",
    ],
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Refresh reporting assets only when their source definition changed
# COMMAND ----------
reporting_source = ROOT / "src" / "schads_audit" / "databricks_io.py"
reporting_fingerprint = _fingerprint_files([reporting_source])

required_reporting_objects = [
    ("gold", "v_latest_audit_runs"),
    ("gold", "v_audit_detail_latest"),
    ("gold", "v_rest_break_findings_latest"),
    ("gold", "v_reconciliation_latest"),
    ("gold", "v_award_scenario_detail_latest"),
    ("gold", "v_award_criteria_detail_latest"),
    ("gold", "v_award_scenario_rest_findings_latest"),
    ("gold", "v_rule_coverage"),
    ("gold", "v_audit_runs"),
    ("gold", "v_readiness_findings"),
    ("semantic", "audit_detail"),
    ("semantic", "payroll_compliance"),
    ("semantic", "rest_break_compliance"),
    ("semantic", "award_scenarios"),
]
reporting_state = _state_get("core_reporting_views")
reporting_current = (
    reporting_state is not None
    and reporting_state["resource_version"] == reporting_fingerprint
    and all(_object_exists(schema, name) for schema, name in required_reporting_objects)
)

if reporting_current:
    print(f"SKIP   core reporting / metric views already current ({reporting_fingerprint[:12]})")
else:
    create_views(spark, catalog)
    create_metric_views(spark, catalog)
    _state_put(
        "core_reporting_views",
        reporting_fingerprint,
        {"objects": [f"{s}.{n}" for s, n in required_reporting_objects]},
    )
    print(f"REFRESH governed reporting / metric views ({reporting_fingerprint[:12]})")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Record core Setup completion
# MAGIC Genie, investigation, simulation, pay-review and dashboard validation are separate Setup job tasks so each failure is reported by its own task key.
# COMMAND ----------
_state_put("setup_build", SETUP_BUILD, {"core_setup": "complete"})

print("AuditHero core Databricks setup complete")
print(f"Setup build:               {SETUP_BUILD}")
print(f"Raw upload folder:         {raw_import_root}")
print(f"Automatic audit workspace: {auto_input_root}")
print("Existing persistent resources were skipped; only missing/migrated/version-changed resources were touched.")
print("Next Setup job tasks configure Genie and dashboard/reporting extensions independently.")
