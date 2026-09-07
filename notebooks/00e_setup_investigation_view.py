# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Interactive Investigation View
# MAGIC
# MAGIC **Purpose:** create the denormalized Gold view used by the interactive AI/BI investigation dashboard.
# MAGIC
# MAGIC The view keeps shift-level audit detail while carrying pay-period reconciliation fields once per employee/pay period.
# MAGIC This notebook is idempotent and skips the rebuild when the current view build already exists.
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"

INVESTIGATION_BUILD = "2026-09-08-investigation-v2"

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


def _exists(schema: str, name: str) -> bool:
    try:
        spark.sql(f"DESCRIBE TABLE `{catalog}`.`{schema}`.`{name}`").limit(1).collect()
        return True
    except Exception:
        return False


state_rows = spark.sql(
    f"""
    SELECT resource_version
    FROM `{catalog}`.`ops`.`setup_state`
    WHERE resource_key = 'audit_investigation_view'
    ORDER BY updated_at DESC
    LIMIT 1
    """
).collect()
current_version = state_rows[0]["resource_version"] if state_rows else None

if current_version == INVESTIGATION_BUILD and _exists("gold", "v_audit_investigation_latest"):
    print(f"SKIP   investigation view already current ({INVESTIGATION_BUILD})")
    dbutils.notebook.exit(f"SKIPPED:{INVESTIGATION_BUILD}")

# COMMAND ----------
spark.sql(
    f"""
    CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_audit_investigation_latest` AS
    WITH ranked_detail AS (
        SELECT
            d.*,
            ROW_NUMBER() OVER (
                PARTITION BY
                    d.audit_run_id,
                    CAST(d.employee_id AS STRING),
                    d.pay_period_start,
                    d.pay_period_end
                ORDER BY d.shift_start, d.timesheet_id
            ) AS pay_period_row_number
        FROM `{catalog}`.`gold`.`v_audit_detail_latest` d
    )
    SELECT
        d.audit_run_id,
        d.run_type,
        d.audit_window_start,
        d.audit_window_end,
        d.run_finished_at,
        CAST(d.employee_id AS STRING) AS employee_id,
        d.employee_name,
        CONCAT(
            COALESCE(d.employee_name, CAST(d.employee_id AS STRING)),
            ' | ',
            COALESCE(CAST(d.pay_period_start AS STRING), 'No pay period')
        ) AS employee_pay_period,
        d.employment_type,
        d.classification_code,
        d.work_group,
        d.state,
        d.holiday_location_key,
        d.timesheet_id,
        d.pay_period_start,
        d.pay_period_end,
        CAST(d.shift_start AS DATE) AS shift_date,
        DATE_FORMAT(d.shift_start, 'EEEE') AS weekday_name,
        d.shift_start,
        d.shift_end,
        d.worked_hours,
        d.sleepover_span_hours,
        d.base_hourly_rate,
        d.expected_amount AS shift_expected_amount,
        d.entitlement_status,
        d.review_flags,
        d.calculation_evidence,
        d.award_reference_date,
        d.industrial_instrument_type,
        d.industrial_instrument_name,
        d.instrument_reference,
        d.instrument_coverage_status,
        d.part_time_pattern_status,
        d.part_time_pattern_reference,
        d.part_time_variation_reference,
        r.expected_amount AS pay_period_expected_amount,
        r.actual_auditable_amount,
        r.variance_actual_minus_expected,
        r.status AS reconciliation_status,
        r.unmapped_pay_categories,
        r.entitlement_review_count,
        CASE WHEN d.pay_period_row_number = 1 THEN 1 ELSE 0 END AS pay_period_marker,
        CASE WHEN d.pay_period_row_number = 1 THEN COALESCE(r.expected_amount, 0) ELSE 0 END AS period_expected_amount_once,
        CASE WHEN d.pay_period_row_number = 1 THEN COALESCE(r.actual_auditable_amount, 0) ELSE 0 END AS actual_auditable_amount_once,
        CASE WHEN d.pay_period_row_number = 1 THEN COALESCE(r.variance_actual_minus_expected, 0) ELSE 0 END AS variance_amount_once,
        CASE
            WHEN d.pay_period_row_number = 1 AND r.status = 'UNDERPAID'
            THEN GREATEST(-COALESCE(r.variance_actual_minus_expected, 0), 0)
            ELSE 0
        END AS underpayment_amount_once,
        CASE
            WHEN d.pay_period_row_number = 1 AND r.status = 'OVERPAID'
            THEN GREATEST(COALESCE(r.variance_actual_minus_expected, 0), 0)
            ELSE 0
        END AS overpayment_amount_once,
        CASE
            WHEN d.pay_period_row_number = 1 AND r.status = 'UNDERPAID' THEN 1 ELSE 0
        END AS underpaid_period_marker,
        CASE
            WHEN d.pay_period_row_number = 1 AND r.status = 'OVERPAID' THEN 1 ELSE 0
        END AS overpaid_period_marker,
        CASE
            WHEN d.pay_period_row_number = 1 AND r.status = 'REQUIRES_REVIEW' THEN 1 ELSE 0
        END AS review_period_marker,
        CASE
            WHEN d.pay_period_row_number = 1 AND r.status IN ('ENTITLEMENT_ONLY','ACTUAL_PAY_UNAVAILABLE') THEN 1 ELSE 0
        END AS entitlement_only_period_marker,
        CASE
            WHEN d.entitlement_status = 'REQUIRES_REVIEW'
              OR COALESCE(TRIM(d.review_flags), '') <> ''
            THEN 1 ELSE 0
        END AS review_shift_marker
    FROM ranked_detail d
    LEFT JOIN `{catalog}`.`gold`.`v_reconciliation_latest` r
      ON d.audit_run_id = r.audit_run_id
     AND CAST(d.employee_id AS STRING) = CAST(r.employee_id AS STRING)
     AND d.pay_period_start <=> r.pay_period_start
     AND d.pay_period_end <=> r.pay_period_end
    """
)

spark.sql(
    f"""
    MERGE INTO `{catalog}`.`ops`.`setup_state` t
    USING (
      SELECT 'audit_investigation_view' AS resource_key,
             '{INVESTIGATION_BUILD}' AS resource_version,
             '{{}}' AS details,
             current_timestamp() AS updated_at
    ) s
    ON t.resource_key = s.resource_key
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
)

count = spark.sql(f"SELECT COUNT(*) AS n FROM `{catalog}`.`gold`.`v_audit_investigation_latest`").first()["n"]
print(f"REFRESH {catalog}.gold.v_audit_investigation_latest ({count} row(s))")
print(f"Investigation view setup complete: {INVESTIGATION_BUILD}")
