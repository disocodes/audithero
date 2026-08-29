# AuditHero — Fabric Setup
#
# PURPOSE
# -------
# Prepare the attached AuditHero Lakehouse for use. Run this notebook after the
# first installation and after an approved AuditHero upgrade.
#
# WHAT IT DOES
# 1. Creates the Lakehouse schemas and stable output tables.
# 2. Validates and loads the effective-dated SCHADS rule reference tables.
# 3. Creates latest-successful-run views and Direct Lake snapshot tables.
# 4. Creates blank administrator control/mapping files when they do not exist.
# 5. Writes a small deployment manifest for support/audit traceability.
#
# It does NOT read employee payroll data and does NOT calculate an audit.

from pathlib import Path
import json

from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.fabric_io import (
    create_lakehouse_objects,
    ensure_output_tables,
    overwrite_rule_tables,
    create_views,
)
from schads_audit.fabric_bi_io import ensure_current_tables

print("STEP 1 — Create/verify Lakehouse schemas and output tables")
create_lakehouse_objects(spark)
ensure_output_tables(spark)
ensure_current_tables(spark)

print("STEP 2 — Validate and load the SCHADS rule library")
# The Fabric package contains the same effective-dated rule packs used by the
# Databricks deployment. Setup stops rather than loading incomplete/malformed rules.
lib = bundled_rule_library()
errors = lib.validate()
if errors:
    raise ValueError("Rule library validation failed:\n" + "\n".join(errors))
overwrite_rule_tables(spark, lib)

print("STEP 3 — Create latest-successful audit views")
# These views are used by reporting/review so a failed rerun does not silently
# replace the last successful audit result.
create_views(spark)

print("STEP 4 — Create administrator configuration templates")
CONFIG = Path("/lakehouse/default/Files/config")
CONFIG.mkdir(parents=True, exist_ok=True)

# JSON mapping files are primarily used by optional Employment Hero API mode.
# Existing files are never overwritten by Setup.
json_templates = {
    "classification_mapping.json": {
        "_instructions": "Source classification name/pay-detail ID -> canonical AuditHero SCHADS classification code"
    },
    "work_type_mapping.json": {
        "_instructions": "Source work type/name -> work_group and optional sleepover facts"
    },
    "work_location_state_mapping.json": {
        "_instructions": "Source location ID -> state and optional holiday_location_key"
    },
    "employee_overrides.json": {
        "_instructions": "Controlled employee facts not reliably available from the source system"
    },
    "pay_category_mapping.json": {
        "_instructions": "Source pay category -> AUDITABLE_WORK, ALLOWANCE or EXCLUDE"
    },
}
for name, body in json_templates.items():
    path = CONFIG / name
    if not path.exists():
        path.write_text(json.dumps(body, indent=2), encoding="utf-8")

# CSV registers hold evidence for conditions that may not exist in basic payroll
# exports. Blank templates are created once and then maintained by the customer.
csv_headers = {
    "public_holiday_overrides.csv": "state,holiday_date,holiday_name,holiday_location_key,holiday_scope,source\n",
    "supplemental_events.csv": "event_id,employee_id,event_type,start_datetime,end_datetime,hours,pay_period_start,pay_period_end,state,holiday_location_key,on_call,training_or_meeting,classification_code,work_group\n",
    "industrial_instrument_history.csv": "employee_id,effective_from,effective_to,instrument_type,instrument_name,award_code,document_reference\n",
    "part_time_patterns.csv": "employee_id,effective_from,effective_to,weekday,start_time,end_time,guaranteed_hours,agreement_reference\n",
    "part_time_variations.csv": "employee_id,shift_date,start_time,end_time,agreement_reference\n",
    "overtime_rest_controls.csv": "employee_id,timesheet_id,shift_start,employer_instructed_resume,evidence_reference\n",
    "meal_break_events.csv": "event_id,employee_id,timesheet_id,mode,scheduled_break_start,actual_break_start,deducted_break_minutes,paid_meal_minutes,evidence_reference\n",
    "toil_register.csv": "agreement_id,employee_id,overtime_datetime,overtime_hours,written_agreement,agreement_date,time_off_hours,time_off_date,payment_requested_date,payment_date,payment_pay_period_start,payment_pay_period_end,employment_end_date,classification_code,employment_type,work_group,state,holiday_location_key,evidence_reference\n",
}
for name, header in csv_headers.items():
    path = CONFIG / name
    if not path.exists():
        path.write_text(header, encoding="utf-8")

print("STEP 5 — Record deployment context")
manifest = {
    "platform": "Microsoft Fabric",
    "lakehouse_id": getattr(notebookutils.runtime.context, "defaultLakehouseId", None),
    "workspace_id": getattr(notebookutils.runtime.context, "currentWorkspaceId", None),
    "rule_pack_count": len(lib.rate_packs) + len(lib.condition_packs) + len(lib.allowance_packs),
}
(CONFIG / "deployment_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("AuditHero Fabric setup complete")
print(f"Loaded {len(lib.rate_packs)} rate packs, {len(lib.condition_packs)} condition packs and {len(lib.allowance_packs)} allowance packs")
print("Raw import folder:      /lakehouse/default/Files/import/raw")
print("Canonical input folder: /lakehouse/default/Files/input")
print("NEXT: run 'AuditHero - Self Test'.")
notebookutils.notebook.exit("success")
