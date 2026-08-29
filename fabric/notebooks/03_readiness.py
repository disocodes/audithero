# AuditHero — API Audit Readiness (Optional API)
#
# PURPOSE
# -------
# Inspect an Employment Hero tenant and show which controlled mappings/evidence are
# still needed before API-sourced historical results can be relied on. This is a
# readiness report, not a payroll calculation. FILES-mode users should run the File
# Readiness pipeline instead.
#
# PARAMETER: key_vault_url — Azure Key Vault used by optional API mode.

from pathlib import Path
import json
import pandas as pd

from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient
from schads_audit.normalize import infer_schads_classification, first
from schads_audit.fabric_io import write_df

print("STEP 1 — Load API configuration and controlled mapping files")
cfg = FabricAuditConfig(key_vault_url=key_vault_url)
config_root = Path(cfg.config_root)


def load_json(name):
    path = config_root / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def csv_has_rows(name):
    path = config_root / name
    if not path.exists():
        return False
    try:
        return not pd.read_csv(path).empty
    except Exception:
        return False


def secret(name):
    return notebookutils.credentials.getSecret(cfg.key_vault_url, name)

client = EmploymentHeroHRClient(
    secret(cfg.hr_client_id_secret),
    secret(cfg.hr_client_secret_secret),
    secret(cfg.hr_refresh_token_secret),
    cfg.hr_base_url,
    cfg.hr_token_url,
)
organisation_id = secret(cfg.organisation_secret)
classification_map = load_json("classification_mapping.json")
pay_map = load_json("pay_category_mapping.json")
work_map = load_json("work_type_mapping.json")
location_map = load_json("work_location_state_mapping.json")

findings = []


def add(kind, key, label, status, detail=""):
    findings.append({
        "finding_type": kind,
        "source_key": str(key or ""),
        "source_label": str(label or ""),
        "status": status,
        "detail": detail,
    })

print("STEP 2 — Check employee classifications and part-time history")
employees = client.employees(organisation_id)
has_part_time = False
for employee in employees:
    employee_id = str(employee.get("id") or "")
    if "PART" in str(first(employee, "employment_type", "employmentType", default="") or "").upper():
        has_part_time = True
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

print("STEP 3 — Check pay category, work type and location mappings")
for row in client.pay_categories(organisation_id):
    source_id = first(row, "id", "Id")
    label = first(row, "name", "display_name", "displayName", "pay_category_name", "payCategoryName")
    mapped = any(key in pay_map for key in (str(source_id or ""), str(label or "")))
    add("PAY_CATEGORY", source_id, label, "READY" if mapped else "MAPPING_REQUIRED", "Map to AUDITABLE_WORK, ALLOWANCE or EXCLUDE")

for row in client.work_types(organisation_id):
    source_id = first(row, "id", "Id")
    label = first(row, "name", "display_name", "displayName")
    mapped = any(key in work_map for key in (str(source_id or ""), str(label or "")))
    add("WORK_TYPE", source_id, label, "READY" if mapped else "MAPPING_RECOMMENDED", "Used for service-stream and sleepover automation")

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

print("STEP 4 — Check historical and conditional evidence registers")
add(
    "CONTROL_REGISTER", "industrial_instrument_history.csv", "industrial_instrument_history.csv",
    "READY" if csv_has_rows("industrial_instrument_history.csv") else "REGISTER_REQUIRED",
    "Record effective-dated Award / enterprise agreement / IFA coverage for the historical population.",
)
if has_part_time:
    add(
        "CONTROL_REGISTER", "part_time_patterns.csv", "part_time_patterns.csv",
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
    add("CONTROL_REGISTER", filename, filename, "READY" if csv_has_rows(filename) else "REGISTER_REVIEW", detail + " An empty register is acceptable only after confirming the event type was not applicable in the audit window.")

print("STEP 5 — Save and display readiness findings")
results = pd.DataFrame(findings).drop_duplicates(["finding_type", "source_key", "source_label"])
results["checked_at"] = pd.Timestamp.utcnow()
write_df(spark, results, "ops.readiness_findings", "overwrite")
display(results.sort_values(["status", "finding_type", "source_label"]))
blocking = results[results.status.isin(["MAPPING_REQUIRED", "REGISTER_REQUIRED"])]
print("\nAUDIT READINESS SUMMARY")
print(results.status.value_counts().to_string())
if len(blocking):
    print(f"\n{len(blocking)} blocking readiness finding(s). Resolve these before relying on historical remediation totals.")
    notebookutils.notebook.exit("review_required")

print("\nBlocking mappings/registers are present. Review recommended/review items, then validate one known payroll period.")
notebookutils.notebook.exit("success")
