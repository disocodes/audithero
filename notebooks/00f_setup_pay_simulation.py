# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Setup Roster Pay Simulation
# MAGIC
# MAGIC Creates the governed simulation and confirmation layer used when roster evidence exists before payroll evidence is available.
# MAGIC Simulated values are never treated as confirmed actual payroll.
# MAGIC
# MAGIC This notebook is idempotent: when the current simulation build and all required objects already exist, it exits without rebuilding them.
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"

SIMULATION_BUILD = "2026-09-08-roster-simulation-v2"

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


def _state_version(key: str):
    rows = spark.sql(
        f"""
        SELECT resource_version
        FROM `{catalog}`.`ops`.`setup_state`
        WHERE resource_key = '{key}'
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).collect()
    return rows[0]["resource_version"] if rows else None


def _put_state(key: str, version: str) -> None:
    spark.sql(
        f"""
        MERGE INTO `{catalog}`.`ops`.`setup_state` t
        USING (
          SELECT '{key}' AS resource_key, '{version}' AS resource_version,
                 '{{}}' AS details, current_timestamp() AS updated_at
        ) s
        ON t.resource_key = s.resource_key
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )


required_objects = [
    ("silver", "pay_rate_confirmations"),
    ("gold", "v_pay_simulation_terms_latest"),
    ("gold", "v_pay_simulation_employee_year"),
    ("gold", "v_pay_rate_confirmations_latest"),
    ("gold", "v_pay_simulation_master"),
]
if _state_version("roster_pay_simulation") == SIMULATION_BUILD and all(
    _exists(schema, name) for schema, name in required_objects
):
    print(f"SKIP   roster pay simulation already current ({SIMULATION_BUILD})")
    dbutils.notebook.exit(f"SKIPPED:{SIMULATION_BUILD}")

# Verify the upstream Award views only when a rebuild is actually required.
required_views = [
    "v_award_scenario_detail_latest",
    "v_award_criteria_detail_latest",
]
for view in required_views:
    spark.sql(f"SELECT 1 FROM `{catalog}`.`gold`.`{view}` LIMIT 1")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Manual/Payroll Rate Confirmation Evidence
# COMMAND ----------
if _exists("silver", "pay_rate_confirmations"):
    print(f"SKIP   table exists: {catalog}.silver.pay_rate_confirmations")
else:
    spark.sql(
        f"""
        CREATE TABLE `{catalog}`.`silver`.`pay_rate_confirmations` (
          confirmation_id STRING,
          employee_id STRING,
          calendar_year INT,
          effective_from DATE,
          effective_to DATE,
          confirmed_hourly_rate DOUBLE,
          pay_model STRING,
          selected_scenario_id STRING,
          source_type STRING,
          source_reference STRING,
          notes STRING,
          confirmed_by STRING,
          confirmed_at TIMESTAMP,
          status STRING,
          supersedes_confirmation_id STRING
        ) USING DELTA
        TBLPROPERTIES (delta.enableChangeDataFeed = true)
        """
    )
    print(f"CREATE table: {catalog}.silver.pay_rate_confirmations")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Shift-level Simulation Terms
# COMMAND ----------
spark.sql(
    f"""
    CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_pay_simulation_terms_latest` AS
    WITH fixed_components AS (
      SELECT
        audit_run_id,
        scenario_id,
        CAST(timesheet_id AS STRING) AS timesheet_id,
        SUM(
          CASE
            WHEN criterion_amount IS NOT NULL AND (
              UPPER(COALESCE(criterion_group, '')) = 'ALLOWANCES'
              OR UPPER(COALESCE(criterion, '')) LIKE '%ALLOWANCE%'
              OR UPPER(COALESCE(criterion, '')) = 'SLEEPOVER_ALLOWANCE'
            )
            THEN criterion_amount
            ELSE 0
          END
        ) AS fixed_award_amount
      FROM `{catalog}`.`gold`.`v_award_criteria_detail_latest`
      GROUP BY audit_run_id, scenario_id, CAST(timesheet_id AS STRING)
    )
    SELECT
      s.audit_run_id,
      s.run_type,
      CAST(s.audit_window_start AS DATE) AS audit_window_start,
      CAST(s.audit_window_end AS DATE) AS audit_window_end,
      CAST(s.employee_id AS STRING) AS employee_id,
      s.employee_name,
      YEAR(s.shift_start) AS calendar_year,
      s.scenario_id,
      s.classification_family,
      s.scenario_classification_code,
      s.scenario_classification_name,
      s.scenario_level,
      s.scenario_pay_point,
      s.scenario_employment_type,
      s.work_group AS scenario_work_group,
      CAST(s.timesheet_id AS STRING) AS timesheet_id,
      s.shift_start,
      s.shift_end,
      COALESCE(s.worked_hours, 0D) AS roster_worked_hours,
      COALESCE(s.sleepover_span_hours, 0D) AS sleepover_span_hours,
      s.base_hourly_rate AS award_minimum_base_rate,
      s.expected_amount AS award_minimum_entitlement,
      COALESCE(f.fixed_award_amount, 0D) AS fixed_award_amount,
      CASE
        WHEN s.base_hourly_rate > 0 AND s.expected_amount IS NOT NULL
        THEN GREATEST((s.expected_amount - COALESCE(f.fixed_award_amount, 0D)) / s.base_hourly_rate, 0D)
        ELSE NULL
      END AS rate_sensitive_factor,
      COALESCE(s.worked_hours, 0D) AS flat_rate_hours,
      s.entitlement_status,
      s.review_flags,
      s.scenario_status,
      CASE
        WHEN s.entitlement_status = 'REQUIRES_REVIEW'
          OR COALESCE(TRIM(s.review_flags), '') <> ''
        THEN 1 ELSE 0
      END AS review_required
    FROM `{catalog}`.`gold`.`v_award_scenario_detail_latest` s
    LEFT JOIN fixed_components f
      ON s.audit_run_id = f.audit_run_id
     AND s.scenario_id = f.scenario_id
     AND CAST(s.timesheet_id AS STRING) = f.timesheet_id
    """
)
print(f"REFRESH view: {catalog}.gold.v_pay_simulation_terms_latest")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Employee / Year / Scenario Simulation Summary
# COMMAND ----------
spark.sql(
    f"""
    CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_pay_simulation_employee_year` AS
    SELECT
      audit_run_id,
      run_type,
      audit_window_start,
      audit_window_end,
      employee_id,
      employee_name,
      calendar_year,
      scenario_id,
      classification_family,
      scenario_classification_code,
      scenario_classification_name,
      scenario_level,
      scenario_pay_point,
      scenario_employment_type,
      scenario_work_group,
      COUNT(DISTINCT timesheet_id) AS roster_shift_count,
      SUM(roster_worked_hours) AS roster_worked_hours,
      MAX(award_minimum_base_rate) AS award_minimum_base_rate,
      SUM(COALESCE(award_minimum_entitlement, 0D)) AS award_minimum_entitlement,
      SUM(COALESCE(fixed_award_amount, 0D)) AS fixed_award_amount,
      SUM(COALESCE(rate_sensitive_factor, 0D)) AS rate_sensitive_factor,
      SUM(COALESCE(flat_rate_hours, 0D)) AS flat_rate_hours,
      SUM(review_required) AS review_shift_count,
      CASE
        WHEN SUM(COALESCE(rate_sensitive_factor, 0D)) > 0
        THEN GREATEST(
          (SUM(COALESCE(award_minimum_entitlement, 0D)) - SUM(COALESCE(fixed_award_amount, 0D)))
          / SUM(COALESCE(rate_sensitive_factor, 0D)),
          0D
        )
        ELSE NULL
      END AS award_structure_break_even_rate,
      CASE
        WHEN SUM(COALESCE(flat_rate_hours, 0D)) > 0
        THEN GREATEST(
          (SUM(COALESCE(award_minimum_entitlement, 0D)) - SUM(COALESCE(fixed_award_amount, 0D)))
          / SUM(COALESCE(flat_rate_hours, 0D)),
          0D
        )
        ELSE NULL
      END AS flat_loaded_break_even_rate
    FROM `{catalog}`.`gold`.`v_pay_simulation_terms_latest`
    GROUP BY
      audit_run_id, run_type, audit_window_start, audit_window_end,
      employee_id, employee_name, calendar_year, scenario_id,
      classification_family, scenario_classification_code, scenario_classification_name,
      scenario_level, scenario_pay_point, scenario_employment_type, scenario_work_group
    """
)
print(f"REFRESH view: {catalog}.gold.v_pay_simulation_employee_year")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Latest Confirmed Rate and Master Simulation View
# COMMAND ----------
spark.sql(
    f"""
    CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_pay_rate_confirmations_latest` AS
    WITH ranked AS (
      SELECT
        c.*,
        ROW_NUMBER() OVER (
          PARTITION BY CAST(employee_id AS STRING), calendar_year
          ORDER BY confirmed_at DESC, confirmation_id DESC
        ) AS rn
      FROM `{catalog}`.`silver`.`pay_rate_confirmations` c
      WHERE COALESCE(status, 'ACTIVE') = 'ACTIVE'
    )
    SELECT * EXCEPT (rn)
    FROM ranked
    WHERE rn = 1
    """
)
print(f"REFRESH view: {catalog}.gold.v_pay_rate_confirmations_latest")

spark.sql(
    f"""
    CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_pay_simulation_master` AS
    SELECT
      e.*,
      c.confirmation_id,
      c.confirmed_hourly_rate,
      c.pay_model AS confirmed_pay_model,
      c.selected_scenario_id,
      c.source_type AS confirmation_source_type,
      c.source_reference AS confirmation_source_reference,
      c.notes AS confirmation_notes,
      c.confirmed_by,
      c.confirmed_at,
      CASE WHEN c.selected_scenario_id = e.scenario_id THEN TRUE ELSE FALSE END AS selected_scenario,
      CASE
        WHEN c.confirmation_id IS NULL THEN NULL
        WHEN c.pay_model = 'FLAT_LOADED_HOURLY'
          THEN e.flat_rate_hours * c.confirmed_hourly_rate + e.fixed_award_amount
        ELSE e.rate_sensitive_factor * c.confirmed_hourly_rate + e.fixed_award_amount
      END AS confirmed_rate_simulated_pay,
      CASE
        WHEN c.confirmation_id IS NULL THEN NULL
        WHEN c.pay_model = 'FLAT_LOADED_HOURLY'
          THEN (e.flat_rate_hours * c.confirmed_hourly_rate + e.fixed_award_amount) - e.award_minimum_entitlement
        ELSE (e.rate_sensitive_factor * c.confirmed_hourly_rate + e.fixed_award_amount) - e.award_minimum_entitlement
      END AS confirmed_rate_variance,
      CASE
        WHEN c.confirmation_id IS NULL THEN 'MISSING_PAY_RATE_CONFIRMATION'
        WHEN c.confirmed_hourly_rate < e.award_minimum_base_rate - 0.005 THEN 'POTENTIAL_BASE_RATE_UNDERPAYMENT'
        WHEN (
          CASE
            WHEN c.pay_model = 'FLAT_LOADED_HOURLY'
              THEN e.flat_rate_hours * c.confirmed_hourly_rate + e.fixed_award_amount
            ELSE e.rate_sensitive_factor * c.confirmed_hourly_rate + e.fixed_award_amount
          END
        ) < e.award_minimum_entitlement - 0.05 THEN 'POTENTIAL_UNDERPAYMENT'
        WHEN e.review_shift_count > 0 THEN 'RATE_CONFIRMED_REQUIRES_AWARD_REVIEW'
        ELSE 'RATE_CONFIRMED_SIMULATION_MEETS_MINIMUM'
      END AS review_status,
      CASE
        WHEN c.confirmation_id IS NULL THEN 'Confirm the employee base hourly rate from payroll, contract or another source. Simulation remains hypothetical.'
        WHEN c.confirmed_hourly_rate < e.award_minimum_base_rate - 0.005 THEN 'Confirmed base rate is below the effective SCHADS minimum for this scenario. Investigate potential underpayment.'
        WHEN (
          CASE
            WHEN c.pay_model = 'FLAT_LOADED_HOURLY'
              THEN e.flat_rate_hours * c.confirmed_hourly_rate + e.fixed_award_amount
            ELSE e.rate_sensitive_factor * c.confirmed_hourly_rate + e.fixed_award_amount
          END
        ) < e.award_minimum_entitlement - 0.05 THEN 'The confirmed rate under the selected pay model does not cover the simulated SCHADS entitlement. Review penalties, overtime and fixed components.'
        WHEN e.review_shift_count > 0 THEN 'Rate simulation meets the numeric minimum but one or more Award/evidence findings still require review.'
        ELSE 'Rate simulation meets the calculated minimum for this scenario. Confirm actual payroll amounts before treating the result as definitive.'
      END AS recommendation
    FROM `{catalog}`.`gold`.`v_pay_simulation_employee_year` e
    LEFT JOIN `{catalog}`.`gold`.`v_pay_rate_confirmations_latest` c
      ON e.employee_id = CAST(c.employee_id AS STRING)
     AND e.calendar_year = c.calendar_year
    """
)
print(f"REFRESH view: {catalog}.gold.v_pay_simulation_master")

_put_state("roster_pay_simulation", SIMULATION_BUILD)

print(f"Roster simulation setup complete: {SIMULATION_BUILD}")
print("Simulation values are hypothetical until a rate is confirmed or actual payroll evidence is loaded.")
print("Use 'AuditHero - Confirm Employee Pay Rate' to save reviewed rate evidence; no Databricks App is required.")
