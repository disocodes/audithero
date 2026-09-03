# AuditHero — Audit Uploaded CSV / Excel
#
# PURPOSE
# -------
# Run the complete AuditHero file audit from canonical inputs. Known employee facts
# drive the definitive audit. In parallel, AuditHero recalculates the supplied shifts
# across SCHADS classification and employment-type scenarios so incomplete employee
# master data does not prevent Award analysis.

from datetime import datetime, timezone
from pathlib import Path
import json
import uuid
import pandas as pd

from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.manual_audit import run_manual_audit
from schads_audit.fabric_io import write_df, create_views
from schads_audit.fabric_bi_io import publish_current_snapshots

run_type = str(globals().get("run_type", "MANUAL_FILE") or "MANUAL_FILE")
input_root = str(globals().get("input_root", "/lakehouse/default/Files/input") or "/lakehouse/default/Files/input")
start_date = str(globals().get("start_date", "") or "").strip()
end_date = str(globals().get("end_date", "") or "").strip()

# Automatic intake writes the detected audit window into its manifest. Explicit
# pipeline parameters take precedence when supplied.
manifest_path = Path(input_root) / "auto_intake_manifest.json"
if (not start_date or not end_date) and manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    start_date = start_date or str(manifest.get("audit_start_date") or manifest.get("start_date") or "")
    end_date = end_date or str(manifest.get("audit_end_date") or manifest.get("end_date") or "")
if not start_date or not end_date:
    raise ValueError(
        "Audit dates could not be determined. Supply start_date/end_date or run the automatic file preparation step first."
    )

print("STEP 1 — Start a traceable audit run")
run_id = str(uuid.uuid4())
started = datetime.now(timezone.utc)
print(f"Run ID: {run_id}")
print(f"Run type: {run_type}")
print(f"Input: {input_root}")
print(f"Audit window: {start_date} to {end_date}")

print("STEP 2 — Calculate definitive entitlements and selectable Award scenarios")
lib = bundled_rule_library()
result = run_manual_audit(
    input_root=input_root,
    config_root="/lakehouse/default/Files/config",
    start_date=start_date,
    end_date=end_date,
    rule_library=lib,
)
finished = datetime.now(timezone.utc)

print("STEP 3 — Add audit-run metadata to calculated outputs")
for frame in (
    result["detail"],
    result["rest_break_findings"],
    result["event_adjustments"],
    result["toil_findings"],
    result["reconciliation"],
    result["award_scenario_detail"],
    result["award_criteria_detail"],
    result["award_scenario_rest_findings"],
):
    if frame is not None and not frame.empty:
        frame["audit_run_id"] = run_id
        frame["audit_window_start"] = str(start_date)[:10]
        frame["audit_window_end"] = str(end_date)[:10]
        frame["run_type"] = run_type
        frame["run_finished_at"] = finished

print("STEP 4 — Persist normalized source evidence")
for name, frame in (
    ("employees", result["employees"]),
    ("pay_details", result["pay_details"]),
    ("employment_history", result["employment_history"]),
    ("timesheets", result["timesheets"]),
    ("rostered_shifts", result["rostered_shifts"]),
    ("payroll_earnings", result["payroll_earnings"]),
    ("public_holidays", result["public_holidays"]),
):
    if frame is not None and not frame.empty:
        persisted = frame.copy()
        persisted["audit_run_id"] = run_id
        persisted["ingested_at"] = finished
        write_df(spark, persisted, f"silver.{name}")

print("STEP 5 — Persist Gold audit, Award scenario and reconciliation results")
write_df(spark, result["detail"], "gold.audit_detail")
write_df(spark, result["rest_break_findings"], "gold.rest_break_findings")
write_df(spark, result["event_adjustments"], "gold.audit_event_adjustments")
write_df(spark, result["toil_findings"], "gold.toil_findings")
write_df(spark, result["reconciliation"], "gold.pay_period_reconciliation")
write_df(spark, result["award_scenario_detail"], "gold.award_scenario_detail")
write_df(spark, result["award_criteria_detail"], "gold.award_criteria_detail")
write_df(spark, result["award_scenario_rest_findings"], "gold.award_scenario_rest_findings")

print("STEP 6 — Record operational run counts")
reconciliation = result["reconciliation"]
rest_findings = result["rest_break_findings"]
scenario_detail = result["award_scenario_detail"]
actual_source = "FILES" if result.get("actual_pay_usable", False) else "NONE"
run = pd.DataFrame([{
    "audit_run_id": run_id,
    "run_type": run_type,
    "audit_window_start": str(start_date)[:10],
    "audit_window_end": str(end_date)[:10],
    "started_at": started,
    "finished_at": finished,
    "status": "SUCCESS",
    "actual_pay_source": actual_source,
    "employees": len(result["employees"]),
    "timesheets": len(result["timesheets"]),
    "underpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "UNDERPAID").sum()),
    "overpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "OVERPAID").sum()),
    "review_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "REQUIRES_REVIEW").sum()),
    "message": f"input={input_root}; rest_findings={len(rest_findings)}; award_scenarios={len(scenario_detail)}",
}])
write_df(spark, run, "ops.audit_runs")
create_views(spark)

print("STEP 7 — Publish the successful audit snapshot for Direct Lake reporting")
publish_current_snapshots(spark, result)

print(f"Uploaded-file audit complete: {run_id}")
if not reconciliation.empty:
    print(reconciliation["status"].value_counts(dropna=False).to_string())
if rest_findings is not None and not rest_findings.empty:
    print("\nRest-between-work findings:")
    print(rest_findings["status"].value_counts(dropna=False).to_string())
if scenario_detail is not None and not scenario_detail.empty:
    print(f"\nAward scenario rows available for interactive analysis: {len(scenario_detail):,}")
print("Recommended next step: open the AuditHero Power BI report and use the Award criteria pages and scenario selectors.")
notebookutils.notebook.exit(run_id)
