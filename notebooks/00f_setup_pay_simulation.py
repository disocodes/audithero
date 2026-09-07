# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Setup Roster Pay Simulation
# MAGIC
# MAGIC Creates the governed simulation/read-back layer used when roster evidence exists before payroll evidence is available.
# MAGIC Simulated values are never treated as confirmed actual payroll.
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("app_service_principal", "")
catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"
app_service_principal = dbutils.widgets.get("app_service_principal").strip()

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
spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS `{catalog}`.`silver`.`pay_rate_confirmations` (
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

# COMMAND ----------
# MAGIC %md
# MAGIC ## Shift-level Simulation Terms
# MAGIC
# MAGIC The Award engine remains authoritative. This view factorises each already-calculated scenario shift into:
# MAGIC
# MAGIC `rate-sensitive factor × hypothetical base rate + fixed Award-linked amount`
# MAGIC
# MAGIC This makes continuous what-if rates effectively instant without storing thousands of duplicate rate rows.
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

# COMMAND ----------
# MAGIC %md
# MAGIC ## Latest Confirmed Rate and Master Review View
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

# COMMAND ----------
# MAGIC %md
# MAGIC ## App Permissions
# COMMAND ----------
if app_service_principal:
    principal = app_service_principal.replace('`', '``')
    grants = [
        f"GRANT USE CATALOG ON CATALOG `{catalog}` TO `{principal}`",
        f"GRANT USE SCHEMA ON SCHEMA `{catalog}`.`gold` TO `{principal}`",
        f"GRANT USE SCHEMA ON SCHEMA `{catalog}`.`silver` TO `{principal}`",
        f"GRANT SELECT ON VIEW `{catalog}`.`gold`.`v_pay_simulation_terms_latest` TO `{principal}`",
        f"GRANT SELECT ON VIEW `{catalog}`.`gold`.`v_pay_simulation_employee_year` TO `{principal}`",
        f"GRANT SELECT ON VIEW `{catalog}`.`gold`.`v_pay_rate_confirmations_latest` TO `{principal}`",
        f"GRANT SELECT ON VIEW `{catalog}`.`gold`.`v_pay_simulation_master` TO `{principal}`",
        f"GRANT SELECT, MODIFY ON TABLE `{catalog}`.`silver`.`pay_rate_confirmations` TO `{principal}`",
    ]
    for statement in grants:
        spark.sql(statement)
    print(f"Granted AuditHero Pay Review app access to {app_service_principal}")
else:
    print("No app_service_principal supplied; created simulation assets without app grants.")

print(f"Created roster simulation views in {catalog}.gold")
print(f"Created confirmation evidence table: {catalog}.silver.pay_rate_confirmations")
print("Simulation values are hypothetical until a rate is confirmed or actual payroll evidence is loaded.")
