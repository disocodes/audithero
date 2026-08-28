# AuditHero Fabric setup notebook
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

create_lakehouse_objects(spark)
ensure_output_tables(spark)
ensure_current_tables(spark)
lib = bundled_rule_library()
errors = lib.validate()
if errors:
    raise ValueError("Rule library validation failed:\n" + "\n".join(errors))
overwrite_rule_tables(spark, lib)
create_views(spark)

CONFIG = Path("/lakehouse/default/Files/config")
CONFIG.mkdir(parents=True, exist_ok=True)

json_templates = {
    "classification_mapping.json": {
        "_instructions": "Employment Hero classification name or pay-detail ID -> canonical SCHADS classification code"
    },
    "work_type_mapping.json": {
        "_instructions": "Employment Hero work type/name -> work_group and optional sleepover facts"
    },
    "work_location_state_mapping.json": {
        "_instructions": "Employment Hero location ID -> state and optional holiday_location_key"
    },
    "employee_overrides.json": {
        "_instructions": "Controlled employee facts not reliably available from Employment Hero"
    },
    "pay_category_mapping.json": {
        "_instructions": "Employment Hero pay category -> AUDITABLE_WORK, ALLOWANCE or EXCLUDE"
    },
}
for name, body in json_templates.items():
    p = CONFIG / name
    if not p.exists():
        p.write_text(json.dumps(body, indent=2), encoding="utf-8")

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
    p = CONFIG / name
    if not p.exists():
        p.write_text(header, encoding="utf-8")

manifest = {
    "platform": "Microsoft Fabric",
    "lakehouse_id": getattr(notebookutils.runtime.context, "defaultLakehouseId", None),
    "workspace_id": getattr(notebookutils.runtime.context, "currentWorkspaceId", None),
    "rule_pack_count": len(lib.rate_packs) + len(lib.condition_packs) + len(lib.allowance_packs),
}
(CONFIG / "deployment_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("AuditHero Fabric Lakehouse initialized")
print(f"Loaded {len(lib.rate_packs)} rate packs, {len(lib.condition_packs)} condition packs, {len(lib.allowance_packs)} allowance packs")
print("Direct Lake snapshot tables are ready under gold.current_*")
print(f"Control files: {CONFIG}")
notebookutils.notebook.exit("success")
