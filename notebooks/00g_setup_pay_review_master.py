# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Setup Employee Pay Review Master
# MAGIC
# MAGIC Creates one dashboard-safe row per audit run / employee / calendar year.
# MAGIC The view prevents the 135 SCHADS scenario rows from inflating confirmation counts.
# MAGIC
# MAGIC This notebook is idempotent and skips the rebuild when the current view build already exists.
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"

PAY_REVIEW_BUILD = "2026-09-08-pay-review-master-v2"

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
    WHERE resource_key = 'pay_review_employee_master'
    ORDER BY updated_at DESC
    LIMIT 1
    """
).collect()
current_version = state_rows[0]["resource_version"] if state_rows else None

if current_version == PAY_REVIEW_BUILD and _exists("gold", "v_pay_review_employee_master"):
    print(f"SKIP   employee pay-review master already current ({PAY_REVIEW_BUILD})")
    dbutils.notebook.exit(f"SKIPPED:{PAY_REVIEW_BUILD}")

spark.sql(f"SELECT 1 FROM `{catalog}`.`gold`.`v_pay_simulation_master` LIMIT 1")

# COMMAND ----------
spark.sql(
    f"""
    CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_pay_review_employee_master` AS
    WITH base AS (
      SELECT *
      FROM `{catalog}`.`gold`.`v_pay_simulation_master`
    ),
    ranges AS (
      SELECT
        audit_run_id,
        MAX(run_type) AS run_type,
        MAX(audit_window_start) AS audit_window_start,
        MAX(audit_window_end) AS audit_window_end,
        employee_id,
        MAX(employee_name) AS employee_name,
        calendar_year,
        COUNT(DISTINCT scenario_id) AS scenario_count,
        MIN(award_minimum_base_rate) AS award_base_rate_low,
        MAX(award_minimum_base_rate) AS award_base_rate_high,
        MIN(award_minimum_entitlement) AS minimum_entitlement_low,
        MAX(award_minimum_entitlement) AS minimum_entitlement_high,
        MIN(award_structure_break_even_rate) AS award_structure_break_even_low,
        MAX(award_structure_break_even_rate) AS award_structure_break_even_high,
        MIN(flat_loaded_break_even_rate) AS flat_loaded_break_even_low,
        MAX(flat_loaded_break_even_rate) AS flat_loaded_break_even_high,
        MAX(CASE WHEN selected_scenario THEN 1 ELSE 0 END) AS has_selected_scenario,
        MAX(CASE WHEN confirmation_id IS NOT NULL THEN 1 ELSE 0 END) AS has_confirmation,
        MAX(confirmation_id) AS confirmation_id,
        MAX(confirmed_hourly_rate) AS confirmed_hourly_rate,
        MAX(confirmed_pay_model) AS confirmed_pay_model,
        MAX(selected_scenario_id) AS selected_scenario_id,
        MAX(confirmation_source_type) AS confirmation_source_type,
        MAX(confirmation_source_reference) AS confirmation_source_reference,
        MAX(confirmation_notes) AS confirmation_notes,
        MAX(confirmed_by) AS confirmed_by,
        MAX(confirmed_at) AS confirmed_at
      FROM base
      GROUP BY audit_run_id, employee_id, calendar_year
    ),
    selected AS (
      SELECT
        b.*,
        ROW_NUMBER() OVER (
          PARTITION BY audit_run_id, employee_id, calendar_year
          ORDER BY CASE WHEN selected_scenario THEN 0 ELSE 1 END, scenario_id
        ) AS rn
      FROM base b
    )
    SELECT
      r.audit_run_id,
      r.run_type,
      r.audit_window_start,
      r.audit_window_end,
      r.employee_id,
      r.employee_name,
      r.calendar_year,
      r.scenario_count,
      r.award_base_rate_low,
      r.award_base_rate_high,
      r.minimum_entitlement_low,
      r.minimum_entitlement_high,
      r.award_structure_break_even_low,
      r.award_structure_break_even_high,
      r.flat_loaded_break_even_low,
      r.flat_loaded_break_even_high,
      r.confirmation_id,
      r.confirmed_hourly_rate,
      r.confirmed_pay_model,
      r.selected_scenario_id,
      r.confirmation_source_type,
      r.confirmation_source_reference,
      r.confirmation_notes,
      r.confirmed_by,
      r.confirmed_at,
      CASE WHEN r.has_selected_scenario = 1 THEN s.classification_family END AS classification_family,
      CASE WHEN r.has_selected_scenario = 1 THEN s.scenario_classification_code END AS scenario_classification_code,
      CASE WHEN r.has_selected_scenario = 1 THEN s.scenario_classification_name END AS scenario_classification_name,
      CASE WHEN r.has_selected_scenario = 1 THEN s.scenario_level END AS scenario_level,
      CASE WHEN r.has_selected_scenario = 1 THEN s.scenario_pay_point END AS scenario_pay_point,
      CASE WHEN r.has_selected_scenario = 1 THEN s.scenario_employment_type END AS scenario_employment_type,
      CASE WHEN r.has_selected_scenario = 1 THEN s.scenario_work_group END AS scenario_work_group,
      CASE WHEN r.has_selected_scenario = 1 THEN s.roster_shift_count END AS roster_shift_count,
      CASE WHEN r.has_selected_scenario = 1 THEN s.roster_worked_hours END AS roster_worked_hours,
      CASE WHEN r.has_selected_scenario = 1 THEN s.award_minimum_base_rate END AS selected_award_minimum_base_rate,
      CASE WHEN r.has_selected_scenario = 1 THEN s.award_minimum_entitlement END AS selected_award_minimum_entitlement,
      CASE WHEN r.has_selected_scenario = 1 THEN s.confirmed_rate_simulated_pay END AS confirmed_rate_simulated_pay,
      CASE WHEN r.has_selected_scenario = 1 THEN s.confirmed_rate_variance END AS confirmed_rate_variance,
      CASE
        WHEN r.has_confirmation = 0 THEN 'MISSING_PAY_RATE_CONFIRMATION'
        WHEN r.has_selected_scenario = 0 THEN 'CONFIRMED_SCENARIO_NOT_IN_CURRENT_RUN'
        ELSE s.review_status
      END AS review_status,
      CASE
        WHEN r.has_confirmation = 0 THEN
          CONCAT(
            'Confirm the employee hourly/base rate and choose the applicable SCHADS scenario. Current roster-only scenario range is ',
            '$', FORMAT_NUMBER(r.minimum_entitlement_low, 2), ' to $', FORMAT_NUMBER(r.minimum_entitlement_high, 2), '.'
          )
        WHEN r.has_selected_scenario = 0 THEN
          'A saved hourly-rate confirmation exists, but its selected SCHADS scenario is not present in this audit run. Re-select and save the applicable scenario.'
        ELSE s.recommendation
      END AS recommendation,
      CASE
        WHEN r.has_confirmation = 0 THEN '🔴 Missing pay-rate confirmation'
        WHEN r.has_selected_scenario = 0 THEN '🟠 Confirmed rate — scenario needs re-selection'
        WHEN s.review_status IN ('POTENTIAL_BASE_RATE_UNDERPAYMENT','POTENTIAL_UNDERPAYMENT') THEN '🔴 Potential underpayment'
        WHEN s.review_status = 'RATE_CONFIRMED_REQUIRES_AWARD_REVIEW' THEN '🟠 Rate confirmed — Award review required'
        ELSE '🟢 Rate simulation meets numeric minimum'
      END AS status_display,
      CASE
        WHEN r.has_confirmation = 0 THEN 3
        WHEN r.has_selected_scenario = 0 THEN 2
        WHEN s.review_status IN ('POTENTIAL_BASE_RATE_UNDERPAYMENT','POTENTIAL_UNDERPAYMENT') THEN 3
        WHEN s.review_status = 'RATE_CONFIRMED_REQUIRES_AWARD_REVIEW' THEN 2
        ELSE 1
      END AS attention_priority
    FROM ranges r
    LEFT JOIN selected s
      ON r.audit_run_id = s.audit_run_id
     AND r.employee_id = s.employee_id
     AND r.calendar_year = s.calendar_year
     AND s.rn = 1
    """
)

spark.sql(
    f"""
    MERGE INTO `{catalog}`.`ops`.`setup_state` t
    USING (
      SELECT 'pay_review_employee_master' AS resource_key,
             '{PAY_REVIEW_BUILD}' AS resource_version,
             '{{}}' AS details,
             current_timestamp() AS updated_at
    ) s
    ON t.resource_key = s.resource_key
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
)

count = spark.sql(f"SELECT COUNT(*) AS n FROM `{catalog}`.`gold`.`v_pay_review_employee_master`").first()["n"]
print(f"REFRESH {catalog}.gold.v_pay_review_employee_master ({count} employee/year/run row(s))")
print(f"Pay-review master setup complete: {PAY_REVIEW_BUILD}")
