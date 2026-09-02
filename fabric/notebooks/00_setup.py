# AuditHero — Fabric Setup
#
# PURPOSE
# -------
# Prepare the attached AuditHero Lakehouse for AuditHero operation.
#
# WHAT IT DOES
# 1. Creates the Lakehouse schemas and output tables.
# 2. Validates and loads the effective-dated SCHADS rule reference tables.
# 3. Creates reporting views and Direct Lake snapshot tables.
# 4. Creates administrator control and mapping templates when they do not exist.
# 5. Records deployment context for traceability.
#
# DATA ACCESS
# ----------
# Setup does not read employee payroll data and does not calculate an audit.

from pathlib import Path
import json
import traceback

stage = "bootstrap"
lib = None


def _runtime_context_value(name):
    """Resolve one Fabric runtime-context value to a JSON-safe string."""
    ctx = notebookutils.runtime.context
    if callable(ctx):
        try:
            resolved = ctx()
            if resolved is not None:
                ctx = resolved
        except Exception:
            pass

    value = None
    if isinstance(ctx, dict):
        value = ctx.get(name)
    else:
        try:
            value = ctx[name]
        except Exception:
            getter = getattr(ctx, "get", None)
            if callable(getter):
                try:
                    value = getter(name)
                except Exception:
                    value = None

        if value is None:
            member = getattr(ctx, name, None)
            if callable(member):
                try:
                    value = member()
                except Exception:
                    value = None
            else:
                value = member

    if value is None:
        return None

    module_name = type(value).__module__
    type_name = type(value).__name__
    if module_name.startswith("py4j") or type_name == "JavaMember":
        return None

    try:
        return str(value).strip() or None
    except Exception:
        return None


try:
    stage = "import AuditHero Fabric package"
    from schads_audit.fabric_rules import bundled_rule_library
    from schads_audit.fabric_io import (
        create_lakehouse_objects,
        ensure_output_tables,
        overwrite_rule_tables,
        create_views,
    )
    from schads_audit.fabric_bi_io import ensure_current_tables

    stage = "STEP 1 — Create/verify Lakehouse schemas and output tables"
    print(stage)
    create_lakehouse_objects(spark)
    ensure_output_tables(spark)
    ensure_current_tables(spark)

    stage = "STEP 2 — Validate and load the SCHADS rule library"
    print(stage)
    lib = bundled_rule_library()
    errors = lib.validate()
    if errors:
        raise ValueError("Rule library validation failed:\n" + "\n".join(errors))
    overwrite_rule_tables(spark, lib)

    stage = "STEP 3 — Create latest-successful audit views"
    print(stage)
    create_views(spark)

    stage = "STEP 4 — Create administrator configuration templates"
    print(stage)
    CONFIG = Path("/lakehouse/default/Files/config")
    CONFIG.mkdir(parents=True, exist_ok=True)

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

    csv_headers = {
        "public_holiday_overrides.csv": "state,holiday_date,holiday_name,holiday_location_key,holiday_scope,source\n",
        "supplemental_events.csv": "event_id,employee_id,event_type,start_datetime,end_datetime,hours,pay_period_start,pay_period_end,state,holiday_location_key,on_call,training_or_meeting,classification_code,work_group\n",
        "industrial_instrument_history.csv": "employee_id,effective_from,effective_to,instrument_type,instrument_name,award_code,document_reference\n",
        "part_time_patterns.csv": "employee_id,effective_from,effective_to,weekday,start_time,end_time,guaranteed_hours,agreement_reference\n",
        "part_time_variations.csv": "employee_id,shift_date,start_time,end_time,agreement_reference\n",
        "rest_break_controls.csv": "employee_id,previous_timesheet_id,next_timesheet_id,shift_start,sleepover_8h_agreement,employer_instructed_resume,release_datetime,evidence_reference\n",
        "overtime_rest_controls.csv": "employee_id,timesheet_id,shift_start,employer_instructed_resume,evidence_reference\n",
        "meal_break_events.csv": "event_id,employee_id,timesheet_id,mode,scheduled_break_start,actual_break_start,deducted_break_minutes,paid_meal_minutes,evidence_reference\n",
        "toil_register.csv": "agreement_id,employee_id,overtime_datetime,overtime_hours,written_agreement,agreement_date,time_off_hours,time_off_date,payment_requested_date,payment_date,payment_pay_period_start,payment_pay_period_end,employment_end_date,classification_code,employment_type,work_group,state,holiday_location_key,evidence_reference\n",
    }
    for name, header in csv_headers.items():
        path = CONFIG / name
        if not path.exists():
            path.write_text(header, encoding="utf-8")

    stage = "STEP 5 — Record deployment context"
    print(stage)
    manifest = {
        "platform": "Microsoft Fabric",
        "lakehouse_id": _runtime_context_value("defaultLakehouseId"),
        "workspace_id": _runtime_context_value("currentWorkspaceId"),
        "rule_pack_count": len(lib.rate_packs) + len(lib.condition_packs) + len(lib.allowance_packs),
    }
    (CONFIG / "deployment_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

except Exception as exc:
    payload = {
        "status": "ERROR",
        "stage": stage,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc()[-12000:],
    }
    print("AUDITHERO SETUP FAILED")
    print(json.dumps(payload, indent=2, default=str))
    notebookutils.notebook.exit("AUDITHERO_ERROR:" + json.dumps(payload, default=str))

else:
    summary = {
        "status": "SUCCESS",
        "rate_packs": len(lib.rate_packs),
        "condition_packs": len(lib.condition_packs),
        "allowance_packs": len(lib.allowance_packs),
    }
    print("AuditHero Fabric setup complete")
    print(
        f"Loaded {summary['rate_packs']} rate packs, "
        f"{summary['condition_packs']} condition packs and "
        f"{summary['allowance_packs']} allowance packs"
    )
    print("Raw import folder:      /lakehouse/default/Files/import/raw")
    print("Canonical input folder: /lakehouse/default/Files/input")
    print("Recommended next step: run 'AuditHero - Self Test'.")
    notebookutils.notebook.exit("AUDITHERO_SUCCESS:" + json.dumps(summary))
