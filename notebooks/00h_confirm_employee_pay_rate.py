# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Confirm Employee Pay Rate
# MAGIC
# MAGIC **Purpose:** persist a reviewed hourly-rate confirmation for one employee/year without requiring a Databricks App.
# MAGIC
# MAGIC This is evidence write-back only. A confirmed hourly rate is **not** treated as proof of complete payroll payment. Full actual-versus-expected reconciliation still requires payroll evidence.
# COMMAND ----------
from pathlib import Path
from datetime import date
import uuid

exec(open(str(Path.cwd() / "_common.py")).read())

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("employee_id", "")
dbutils.widgets.text("calendar_year", "")
dbutils.widgets.text("confirmed_hourly_rate", "")
dbutils.widgets.dropdown(
    "pay_model",
    "BASE_PLUS_SCHADS_MULTIPLIERS",
    ["BASE_PLUS_SCHADS_MULTIPLIERS", "FLAT_LOADED_HOURLY"],
)
dbutils.widgets.text("selected_scenario_id", "")
dbutils.widgets.dropdown(
    "source_type",
    "MANUAL_CONFIRMATION",
    ["MANUAL_CONFIRMATION", "PAYROLL_EXPORT", "PAYSLIP", "EMPLOYMENT_CONTRACT", "OTHER"],
)
dbutils.widgets.text("source_reference", "")
dbutils.widgets.text("notes", "")

catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"
employee_id = dbutils.widgets.get("employee_id").strip()
year_text = dbutils.widgets.get("calendar_year").strip()
rate_text = dbutils.widgets.get("confirmed_hourly_rate").strip()
pay_model = dbutils.widgets.get("pay_model").strip().upper()
selected_scenario_id = dbutils.widgets.get("selected_scenario_id").strip() or None
source_type = dbutils.widgets.get("source_type").strip().upper()
source_reference = dbutils.widgets.get("source_reference").strip() or None
notes = dbutils.widgets.get("notes").strip() or None

if not employee_id:
    raise ValueError("employee_id is required")
try:
    calendar_year = int(year_text)
except Exception as exc:
    raise ValueError("calendar_year must be a four-digit year") from exc
if calendar_year < 2000 or calendar_year > 2100:
    raise ValueError("calendar_year is outside the supported range 2000-2100")
try:
    confirmed_hourly_rate = float(rate_text)
except Exception as exc:
    raise ValueError("confirmed_hourly_rate must be numeric") from exc
if confirmed_hourly_rate <= 0 or confirmed_hourly_rate > 500:
    raise ValueError("confirmed_hourly_rate must be greater than 0 and no more than $500/hour")
if pay_model not in {"BASE_PLUS_SCHADS_MULTIPLIERS", "FLAT_LOADED_HOURLY"}:
    raise ValueError("Unsupported pay_model")

# COMMAND ----------
# Confirm the employee/year exists in the current simulation data. Scenario selection
# is optional because a user may know the historical hourly rate before establishing
# the correct SCHADS classification scenario.
simulation_rows = spark.sql(
    f"""
    SELECT scenario_id, scenario_classification_name, scenario_level, scenario_pay_point,
           scenario_employment_type, award_minimum_base_rate, award_minimum_entitlement
    FROM `{catalog}`.`gold`.`v_pay_simulation_employee_year`
    WHERE CAST(employee_id AS STRING) = ? AND calendar_year = ?
    ORDER BY scenario_classification_name, scenario_level, scenario_pay_point, scenario_employment_type
    """,
    args=[employee_id, calendar_year],
).collect()
if not simulation_rows:
    raise ValueError(
        f"No roster-pay simulation rows exist for employee_id={employee_id!r}, year={calendar_year}. "
        "Run the roster/file audit for that period first."
    )

if selected_scenario_id:
    scenario = next((r for r in simulation_rows if str(r["scenario_id"]) == selected_scenario_id), None)
    if scenario is None:
        raise ValueError(
            f"selected_scenario_id={selected_scenario_id!r} is not available for employee {employee_id} in {calendar_year}."
        )

# COMMAND ----------
# Persist a new evidence record. Existing confirmations are not deleted: the latest
# active record wins, while supersedes_confirmation_id preserves the review trail.
latest = spark.sql(
    f"""
    SELECT confirmation_id
    FROM `{catalog}`.`silver`.`pay_rate_confirmations`
    WHERE CAST(employee_id AS STRING) = ?
      AND calendar_year = ?
      AND COALESCE(status, 'ACTIVE') = 'ACTIVE'
    ORDER BY confirmed_at DESC, confirmation_id DESC
    LIMIT 1
    """,
    args=[employee_id, calendar_year],
).first()

confirmation_id = f"PAYRATE-{uuid.uuid4().hex.upper()}"
supersedes = str(latest["confirmation_id"]) if latest else None
confirmed_by = spark.sql("SELECT current_user() AS user_name").first()["user_name"]

effective_from = date(calendar_year, 1, 1)
effective_to = date(calendar_year, 12, 31)

payload = spark.createDataFrame(
    [
        (
            confirmation_id,
            employee_id,
            calendar_year,
            effective_from,
            effective_to,
            confirmed_hourly_rate,
            pay_model,
            selected_scenario_id,
            source_type,
            source_reference,
            notes,
            str(confirmed_by),
            "ACTIVE",
            supersedes,
        )
    ],
    """
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
    status STRING,
    supersedes_confirmation_id STRING
    """,
).withColumn("confirmed_at", __import__("pyspark").sql.functions.current_timestamp())

payload.select(
    "confirmation_id", "employee_id", "calendar_year", "effective_from", "effective_to",
    "confirmed_hourly_rate", "pay_model", "selected_scenario_id", "source_type",
    "source_reference", "notes", "confirmed_by", "confirmed_at", "status",
    "supersedes_confirmation_id",
).write.format("delta").mode("append").saveAsTable(f"{catalog}.silver.pay_rate_confirmations")

print("Saved AuditHero pay-rate confirmation")
print(f"  confirmation_id:      {confirmation_id}")
print(f"  employee_id:          {employee_id}")
print(f"  calendar_year:        {calendar_year}")
print(f"  confirmed_hourly_rate: ${confirmed_hourly_rate:,.2f}")
print(f"  pay_model:            {pay_model}")
print(f"  selected_scenario_id: {selected_scenario_id or 'NOT YET CONFIRMED'}")
print(f"  evidence_source:      {source_type}")
print(f"  confirmed_by:         {confirmed_by}")
if supersedes:
    print(f"  supersedes:           {supersedes}")
print("Refresh AuditHero - SCHADS Payroll Compliance to see the updated employee/year review status.")
