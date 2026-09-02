from __future__ import annotations
import json
import pandas as pd


def _sql(spark, label: str, statement: str):
    """Execute Spark SQL and preserve the exact failing operation in errors."""
    try:
        return spark.sql(statement)
    except Exception as exc:
        compact = " ".join(statement.split())
        raise RuntimeError(f"Fabric Spark SQL failed while {label}: {compact}") from exc


def create_lakehouse_objects(spark):
    """Create AuditHero schemas in the notebook's attached schema-enabled Lakehouse."""
    for schema in ("bronze", "silver", "ref", "gold", "ops"):
        _sql(
            spark,
            f"creating schema {schema}",
            f"CREATE SCHEMA IF NOT EXISTS `{schema}`",
        )


def write_df(spark, df: pd.DataFrame, table: str, mode: str = "append"):
    if df is None or df.empty:
        return
    clean = df.copy()
    for col in clean.columns:
        if clean[col].dtype == "object":
            clean[col] = clean[col].where(clean[col].notna(), None)
    try:
        spark.createDataFrame(clean).write.format("delta").mode(mode).option(
            "mergeSchema", "true"
        ).saveAsTable(table)
    except Exception as exc:
        raise RuntimeError(
            f"Fabric Delta write failed for {table} in {mode} mode "
            f"({len(clean)} rows, columns={list(clean.columns)})"
        ) from exc


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
    statements = [
        (
            "creating ops.audit_runs",
            """
            CREATE TABLE IF NOT EXISTS ops.audit_runs (
              audit_run_id STRING, run_type STRING, audit_window_start STRING,
              audit_window_end STRING, started_at TIMESTAMP, finished_at TIMESTAMP,
              status STRING, actual_pay_source STRING, employees BIGINT,
              timesheets BIGINT, underpaid_periods BIGINT, overpaid_periods BIGINT,
              review_periods BIGINT, message STRING
            ) USING DELTA
            """,
        ),
        (
            "creating gold.audit_detail",
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
            """,
        ),
        (
            "creating gold.audit_event_adjustments",
            """
            CREATE TABLE IF NOT EXISTS gold.audit_event_adjustments (
              event_id STRING, employee_id STRING, employee_name STRING,
              event_type STRING, pay_period_start TIMESTAMP, pay_period_end TIMESTAMP,
              expected_adjustment DOUBLE, event_status STRING, review_flags STRING,
              calculation_evidence STRING, audit_run_id STRING,
              audit_window_start STRING, audit_window_end STRING, run_type STRING,
              run_finished_at TIMESTAMP
            ) USING DELTA
            """,
        ),
        (
            "creating gold.toil_findings",
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
            """,
        ),
        (
            "creating gold.rest_break_findings",
            """
            CREATE TABLE IF NOT EXISTS gold.rest_break_findings (
              finding_id STRING, finding_type STRING, employee_id STRING,
              employee_name STRING, previous_timesheet_ids STRING,
              next_timesheet_ids STRING, previous_shift_end TIMESTAMP,
              next_shift_start TIMESTAMP, required_rest_hours DOUBLE,
              actual_rest_hours DOUBLE, rest_shortfall_hours DOUBLE,
              sleepover_adjacent_exception_eligible BOOLEAN,
              sleepover_8h_agreement BOOLEAN, sleepover_blocked_rest BOOLEAN,
              historical_sleepover_interaction BOOLEAN,
              overtime_rest_rule_applies BOOLEAN, employer_instructed_resume BOOLEAN,
              release_datetime TIMESTAMP, double_time_repriced_hours DOUBLE,
              double_time_topup DOUBLE, paid_absence_rostered_hours DOUBLE,
              payment_status STRING, status STRING, clause STRING,
              overtime_clause STRING, evidence_reference STRING, notes STRING,
              audit_run_id STRING, audit_window_start STRING, audit_window_end STRING,
              run_type STRING, run_finished_at TIMESTAMP
            ) USING DELTA
            """,
        ),
        (
            "creating gold.pay_period_reconciliation",
            """
            CREATE TABLE IF NOT EXISTS gold.pay_period_reconciliation (
              employee_id STRING, employee_name STRING, pay_period_start TIMESTAMP,
              pay_period_end TIMESTAMP, expected_amount DOUBLE, shift_count BIGINT,
              entitlement_review_count BIGINT, actual_auditable_amount DOUBLE,
              unmapped_pay_categories STRING, variance_actual_minus_expected DOUBLE,
              status STRING, audit_run_id STRING, audit_window_start STRING,
              audit_window_end STRING, run_type STRING, run_finished_at TIMESTAMP
            ) USING DELTA
            """,
        ),
        (
            "creating ops.readiness_findings",
            """
            CREATE TABLE IF NOT EXISTS ops.readiness_findings (
              finding_type STRING, source_key STRING, source_label STRING,
              status STRING, detail STRING, checked_at TIMESTAMP
            ) USING DELTA
            """,
        ),
    ]
    for label, statement in statements:
        _sql(spark, label, statement)


def create_views(spark):
    # Reporting views select the latest successful run for each audit window.
    statements = [
        (
            "creating gold.v_latest_audit_runs",
            """
            CREATE OR REPLACE VIEW gold.v_latest_audit_runs AS
            SELECT *
            FROM (
              SELECT r.*,
                     ROW_NUMBER() OVER (
                       PARTITION BY audit_window_start, audit_window_end
                       ORDER BY finished_at DESC
                     ) AS __audithero_row_number
              FROM ops.audit_runs r
              WHERE status='SUCCESS'
            ) ranked
            WHERE __audithero_row_number = 1
            """,
        ),
        (
            "creating gold.v_audit_detail_latest",
            """
            CREATE OR REPLACE VIEW gold.v_audit_detail_latest AS
            SELECT d.* FROM gold.audit_detail d
            INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
            """,
        ),
        (
            "creating gold.v_reconciliation_latest",
            """
            CREATE OR REPLACE VIEW gold.v_reconciliation_latest AS
            SELECT d.* FROM gold.pay_period_reconciliation d
            INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
            """,
        ),
        (
            "creating gold.v_event_adjustments_latest",
            """
            CREATE OR REPLACE VIEW gold.v_event_adjustments_latest AS
            SELECT d.* FROM gold.audit_event_adjustments d
            INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
            """,
        ),
        (
            "creating gold.v_toil_findings_latest",
            """
            CREATE OR REPLACE VIEW gold.v_toil_findings_latest AS
            SELECT d.* FROM gold.toil_findings d
            INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
            """,
        ),
        (
            "creating gold.v_rest_break_findings_latest",
            """
            CREATE OR REPLACE VIEW gold.v_rest_break_findings_latest AS
            SELECT d.* FROM gold.rest_break_findings d
            INNER JOIN gold.v_latest_audit_runs r ON d.audit_run_id=r.audit_run_id
            """,
        ),
        (
            "creating gold.v_exception_periods",
            """
            CREATE OR REPLACE VIEW gold.v_exception_periods AS
            SELECT * FROM gold.v_reconciliation_latest
            WHERE status IN ('UNDERPAID','OVERPAID','REQUIRES_REVIEW','ACTUAL_PAY_UNAVAILABLE')
            """,
        ),
        (
            "creating gold.v_employee_month",
            """
            CREATE OR REPLACE VIEW gold.v_employee_month AS
            SELECT date_trunc('MONTH',shift_start) month, employee_id, employee_name,
                   sum(expected_amount) expected_amount, count(*) shifts,
                   sum(CASE WHEN entitlement_status='REQUIRES_REVIEW' THEN 1 ELSE 0 END) review_shifts
            FROM gold.v_audit_detail_latest
            GROUP BY date_trunc('MONTH',shift_start), employee_id, employee_name
            """,
        ),
    ]
    for label, statement in statements:
        _sql(spark, label, statement)
