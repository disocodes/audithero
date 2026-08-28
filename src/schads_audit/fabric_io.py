from __future__ import annotations
import json
import pandas as pd


def create_lakehouse_objects(spark):
    """Create AuditHero schemas in the notebook's attached schema-enabled Lakehouse."""
    for schema in ("bronze", "silver", "ref", "gold", "ops"):
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{schema}`")


def write_df(spark, df: pd.DataFrame, table: str, mode: str = "append"):
    if df is None or df.empty:
        return
    clean = df.copy()
    for col in clean.columns:
        if clean[col].dtype == "object":
            clean[col] = clean[col].where(clean[col].notna(), None)
    spark.createDataFrame(clean).write.format("delta").mode(mode).option(
        "mergeSchema", "true"
    ).saveAsTable(table)


def overwrite_rule_tables(spark, rule_library):
    rate_rows = []
    for pack in rule_library.rate_packs:
        for row in pack["rates"]:
            x = dict(row)
            x.update(
                {
                    "award_code": pack["award_code"],
                    "rate_pack_id": pack["rate_pack_id"],
                    "operative_date": pack["operative_date"],
                    "application_basis": pack["application_basis"],
                    "source_json": json.dumps(pack.get("source", {})),
                }
            )
            rate_rows.append(x)
    condition_rows = [
        {
            "award_code": p["award_code"],
            "condition_pack_id": p["condition_pack_id"],
            "operative_date": p["operative_date"],
            "condition_json": json.dumps(p),
        }
        for p in rule_library.condition_packs
    ]
    allowance_rows = []
    for pack in rule_library.allowance_packs:
        for row in pack["allowances"]:
            x = dict(row)
            x.update(
                {
                    "award_code": pack["award_code"],
                    "allowance_pack_id": pack["allowance_pack_id"],
                    "operative_date": pack["operative_date"],
                    "source_json": json.dumps(pack.get("source", {})),
                }
            )
            allowance_rows.append(x)
    write_df(spark, pd.DataFrame(rate_rows), "ref.rates", "overwrite")
    write_df(spark, pd.DataFrame(condition_rows), "ref.conditions", "overwrite")
    write_df(spark, pd.DataFrame(allowance_rows), "ref.allowances", "overwrite")
    write_df(
        spark,
        pd.DataFrame(rule_library.coverage_rows()),
        "ref.rule_coverage",
        "overwrite",
    )


def ensure_output_tables(spark):
    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS ops.audit_runs (
          audit_run_id STRING, run_type STRING, audit_window_start STRING,
          audit_window_end STRING, started_at TIMESTAMP, finished_at TIMESTAMP,
          status STRING, actual_pay_source STRING, employees BIGINT,
          timesheets BIGINT, underpaid_periods BIGINT, overpaid_periods BIGINT,
          review_periods BIGINT, message STRING
        ) USING DELTA
        """
    )
    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS gold.audit_detail (
          timesheet_id STRING, employee_id STRING, employee_name STRING,
          employment_type STRING, classification_code STRING, work_group STRING,
          state STRING, holiday_location_key STRING, pay_period_start TIMESTAMP,
          pay_period_end TIMESTAMP, award_reference_date TIMESTAMP,
          shift_start TIMESTAMP, shift_end TIMESTAMP, worked_hours DOUBLE,
          sleepover_span_hours DOUBLE, base_hourly_rate DOUBLE,
          expected_amount DOUBLE, entitlement_status STRING, review_flags STRING,
          calculation_evidence STRING, industrial_instrument_type STRING,
          industrial_instrument_name STRING, instrument_reference STRING,
          instrument_coverage_status STRING, part_time_pattern_status STRING,
          part_time_pattern_reference STRING, part_time_variation_reference STRING,
          audit_run_id STRING, audit_window_start STRING, audit_window_end STRING,
          run_type STRING, run_finished_at TIMESTAMP
        ) USING DELTA
        """
    )
    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS gold.audit_event_adjustments (
          event_id STRING, employee_id STRING, employee_name STRING,
          event_type STRING, pay_period_start TIMESTAMP, pay_period_end TIMESTAMP,
          expected_adjustment DOUBLE, event_status STRING, review_flags STRING,
          calculation_evidence STRING, audit_run_id STRING,
          audit_window_start STRING, audit_window_end STRING, run_type STRING,
          run_finished_at TIMESTAMP
        ) USING DELTA
        """
    )
    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS gold.toil_findings (
          toil_agreement_id STRING, employee_id STRING, employee_name STRING,
          overtime_datetime TIMESTAMP, overtime_hours DOUBLE, time_off_hours DOUBLE,
          remaining_hours DOUBLE, deadline TIMESTAMP, payment_date TIMESTAMP,
          payment_reason STRING, expected_adjustment DOUBLE, status STRING,
          review_flags STRING, calculation_evidence STRING,
          pay_period_start TIMESTAMP, pay_period_end TIMESTAMP,
          audit_run_id STRING, audit_window_start STRING, audit_window_end STRING,
          run_type STRING, run_finished_at TIMESTAMP
        ) USING DELTA
        """
    )
    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS gold.pay_period_reconciliation (
          employee_id STRING, employee_name STRING, pay_period_start TIMESTAMP,
          pay_period_end TIMESTAMP, expected_amount DOUBLE, shift_count BIGINT,
          entitlement_review_count BIGINT, actual_auditable_amount DOUBLE,
          unmapped_pay_categories STRING, variance_actual_minus_expected DOUBLE,
          status STRING, audit_run_id STRING, audit_window_start STRING,
          audit_window_end STRING, run_type STRING, run_finished_at TIMESTAMP
        ) USING DELTA
        """
    )
    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS ops.readiness_findings (
          finding_type STRING, source_key STRING, source_label STRING,
          status STRING, detail STRING, checked_at TIMESTAMP
        ) USING DELTA
        """
    )


def create_views(spark):
    spark.sql(
        """
        CREATE OR REPLACE VIEW gold.v_latest_audit_runs AS
        SELECT * FROM ops.audit_runs
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY audit_window_start, audit_window_end
          ORDER BY finished_at DESC
        ) = 1
        """
    )
    spark.sql(
        """
        CREATE OR REPLACE VIEW gold.v_audit_detail_latest AS
        SELECT d.* FROM gold.audit_detail d
        INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
        WHERE r.status='SUCCESS'
        """
    )
    spark.sql(
        """
        CREATE OR REPLACE VIEW gold.v_reconciliation_latest AS
        SELECT d.* FROM gold.pay_period_reconciliation d
        INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
        WHERE r.status='SUCCESS'
        """
    )
    spark.sql(
        """
        CREATE OR REPLACE VIEW gold.v_event_adjustments_latest AS
        SELECT d.* FROM gold.audit_event_adjustments d
        INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
        WHERE r.status='SUCCESS'
        """
    )
    spark.sql(
        """
        CREATE OR REPLACE VIEW gold.v_toil_findings_latest AS
        SELECT d.* FROM gold.toil_findings d
        INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
        WHERE r.status='SUCCESS'
        """
    )
    spark.sql(
        """
        CREATE OR REPLACE VIEW gold.v_exception_periods AS
        SELECT * FROM gold.v_reconciliation_latest
        WHERE status IN ('UNDERPAID','OVERPAID','REQUIRES_REVIEW','ACTUAL_PAY_UNAVAILABLE')
        """
    )
    spark.sql(
        """
        CREATE OR REPLACE VIEW gold.v_employee_month AS
        SELECT date_trunc('MONTH',shift_start) month, employee_id, employee_name,
               sum(expected_amount) expected_amount, count(*) shifts,
               sum(CASE WHEN entitlement_status='REQUIRES_REVIEW' THEN 1 ELSE 0 END) review_shifts
        FROM gold.v_audit_detail_latest
        GROUP BY ALL
        """
    )
