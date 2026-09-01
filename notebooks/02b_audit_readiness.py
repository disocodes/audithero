# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — API Audit Readiness (Optional API)
# MAGIC
# MAGIC **Purpose:** inspect Employment Hero data and identify classifications, pay categories, work types, work locations and controlled evidence that require configuration before API-sourced audit results are used.
# MAGIC
# MAGIC This is a readiness report, not a payroll calculation. For uploaded-file audits, use **AuditHero - File Readiness**.
# COMMAND ----------
# MAGIC %pip install "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

import json
import pandas as pd
from schads_audit.config import AuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient
from schads_audit.normalize import infer_schads_classification, first
from schads_audit.databricks_io import write_df
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Connect to Employment Hero and load controlled mappings
# MAGIC
# MAGIC API metadata is compared with the mapping files in `config/`. Missing pay-category treatment, classification mapping or controlled evidence remains a readiness finding until it is configured.
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("secret_scope", "audithero")
catalog = dbutils.widgets.get("catalog")
scope = dbutils.widgets.get("secret_scope")
cfg = AuditConfig(catalog=catalog, secret_scope=scope)


def secret(key):
    return dbutils.secrets.get(scope=scope, key=key)

client = EmploymentHeroHRClient(
    secret("EH_HR_CLIENT_ID"),
    secret("EH_HR_CLIENT_SECRET"),
    secret("EH_HR_REFRESH_TOKEN"),
    cfg.hr_base_url,
    cfg.hr_token_url,
)
organisation_id = secret("EH_ORGANISATION_ID")


def load_json(name):
    path = ROOT / "config" / name
    return json.loads(path.read_text()) if path.exists() else {}


def csv_has_rows(name):
    path = ROOT / "config" / name
    if not path.exists():
        return False
    try:
        return not pd.read_csv(path).empty
    except Exception:
        return False

classification_map = load_json("classification_mapping.json")
pay_map = load_json("pay_category_mapping.json")
work_map = load_json("work_type_mapping.json")
location_map = load_json("work_location_state_mapping.json")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Check employee classifications and part-time history
# MAGIC
# MAGIC Each Employment Hero classification must resolve to a supported AuditHero classification. Employment history is also checked to determine whether effective-dated part-time pattern evidence is required.
# COMMAND ----------
findings = []


def add(kind, key, label, status, detail=""):
    findings.append({"finding_type": kind, "source_key": str(key or ""), "source_label": str(label or ""), "status": status, "detail": detail})

employees = client.employees(organisation_id)
employee_ids = [str(x.get("id")) for x in employees if x.get("id")]
has_part_time = any("PART" in str(first(emp, "employment_type", "employmentType", default="") or "").upper() for emp in employees)

for employee_id in employee_ids:
    for history_row in client.employment_histories(organisation_id, employee_id):
        if "PART" in str(first(history_row, "employment_type", "employmentType", default="") or "").upper():
            has_part_time = True
    for pay_row in client.pay_details(organisation_id, employee_id):
        label = first(pay_row, "classification", "classification_name", "classificationName")
        source_id = first(pay_row, "id", "Id")
        resolved = None
        for key in (str(source_id or ""), str(label or "")):
            if key in classification_map:
                value = classification_map[key]
                resolved = value.get("classification_code") if isinstance(value, dict) else value
                break
        resolved = resolved or infer_schads_classification(label)
        add("CLASSIFICATION", source_id, label, "READY" if resolved else "MAPPING_REQUIRED", resolved or "No canonical SCHADS classification resolved")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Check payroll, work-type and location mappings
# MAGIC
# MAGIC Pay-category treatment is required for actual-pay reconciliation. Work-type mappings support service-stream and sleepover analysis. Work-location mappings provide state and optional local-holiday context.
# COMMAND ----------
for row in client.pay_categories(organisation_id):
    source_id = first(row, "id", "Id")
    label = first(row, "name", "display_name", "displayName", "pay_category_name", "payCategoryName")
    mapped = any(key in pay_map for key in (str(source_id or ""), str(label or "")))
    add("PAY_CATEGORY", source_id, label, "READY" if mapped else "MAPPING_REQUIRED", "Map to AUDITABLE_WORK, ALLOWANCE or EXCLUDE")

for row in client.work_types(organisation_id):
    source_id = first(row, "id", "Id")
    label = first(row, "name", "display_name", "displayName")
    mapped = any(key in work_map for key in (str(source_id or ""), str(label or "")))
    add("WORK_TYPE", source_id, label, "READY" if mapped else "MAPPING_RECOMMENDED", "Used for service-stream and sleepover analysis")

for row in client.work_locations(organisation_id):
    source_id = first(row, "id", "Id")
    label = first(row, "name", "display_name", "displayName")
    config_row = location_map.get(str(source_id or ""))
    state_ready = isinstance(config_row, dict) and bool(config_row.get("state"))
    if not state_ready:
        add("WORK_LOCATION", source_id, label, "MAPPING_REQUIRED", "State is required for public-holiday auditing")
    else:
        location_key = config_row.get("holiday_location_key")
        detail = f"state={config_row.get('state')}" + (f"; holiday_location_key={location_key}" if location_key else "; no local holiday key configured")
        add("WORK_LOCATION", source_id, label, "READY" if location_key else "MAPPING_RECOMMENDED", detail)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Check historical and conditional evidence registers
# MAGIC
# MAGIC Instrument history is required for historical coverage checks. Part-time pattern evidence is required when part-time employment exists. Other event registers can remain empty when the relevant event did not occur in the audit period.
# COMMAND ----------
add(
    "CONTROL_REGISTER",
    "industrial_instrument_history.csv",
    "industrial_instrument_history.csv",
    "READY" if csv_has_rows("industrial_instrument_history.csv") else "REGISTER_REQUIRED",
    "Record effective-dated Award / enterprise agreement / IFA coverage for the historical population.",
)

if has_part_time:
    add(
        "CONTROL_REGISTER",
        "part_time_patterns.csv",
        "part_time_patterns.csv",
        "READY" if csv_has_rows("part_time_patterns.csv") else "REGISTER_REQUIRED",
        "Part-time employment exists; load effective-dated written guaranteed-hours patterns.",
    )
else:
    add("CONTROL_REGISTER", "part_time_patterns.csv", "part_time_patterns.csv", "READY" if csv_has_rows("part_time_patterns.csv") else "NOT_APPLICABLE", "No part-time employment was found in Employment Hero history.")

for filename, detail in {
    "overtime_rest_controls.csv": "Populate when an employee is directed to resume before the required post-overtime rest period.",
    "meal_break_events.csv": "Populate worked-through/client-meal exceptions when applicable.",
    "toil_register.csv": "Populate written TOIL agreements when TOIL is used.",
    "supplemental_events.csv": "Populate recall, on-call, remote work, active sleepover work or other controlled events when applicable.",
}.items():
    add("CONTROL_REGISTER", filename, filename, "READY" if csv_has_rows(filename) else "REGISTER_REVIEW", detail + " An empty register is acceptable when the event type did not occur in the audit window.")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Save and display readiness findings
# MAGIC
# MAGIC Findings are written to `ops.readiness_findings`. `MAPPING_REQUIRED` and `REGISTER_REQUIRED` must be resolved before a dependable historical reconciliation is produced.
# COMMAND ----------
out = pd.DataFrame(findings).drop_duplicates(["finding_type", "source_key", "source_label"])
out["checked_at"] = pd.Timestamp.utcnow()
write_df(spark, out, f"{catalog}.ops.readiness_findings", "overwrite")
display(out.sort_values(["status", "finding_type", "source_label"]))

blocking = out[out.status.isin(["MAPPING_REQUIRED", "REGISTER_REQUIRED"])]
print("\nAUDIT READINESS SUMMARY")
print(out.status.value_counts().to_string())
if len(blocking):
    print(f"\nResolve {len(blocking)} blocking mapping/register item(s) before relying on historical reconciliation totals.")
else:
    print("\nNo blocking mapping/register findings remain. Review recommended items, then validate one known payroll period.")
