# AuditHero — Audit Uploaded CSV / Excel
#
# PURPOSE
# -------
# Main credential-free AuditHero audit for canonical files. The standard Fabric
# pipeline runs File Readiness first, then calls this notebook with input_root and
# the requested date range.
#
# This notebook uses the shared AuditHero calculation engine, persists normalized
# evidence/results, records the run and replaces the Direct Lake current snapshot
# only after the audit completes successfully.

from datetime import datetime, timezone
import uuid
import pandas as pd

from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.manual_audit import run_manual_audit
from schads_audit.fabric_io import write_df, create_views
from schads_audit.fabric_bi_io import publish_current_snapshots

print("STEP 1 — Start a traceable audit run")
run_id = str(uuid.uuid4())
started = datetime.now(timezone.utc)
print(f"Run ID: {run_id}")
print(f"Input: {input_root}")
print(f"Audit window: {start_date} to {end_date}")

print("STEP 2 — Calculate expected entitlements and reconcile actual payroll")
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
for frame in (result["detail"], result["event_adjustments"], result["toil_findings"], result["reconciliation"]):
    if frame is not None and not frame.empty:
        frame["audit_run_id"] = run_id
        frame["audit_window_start"] = str(start_date)[:10]
        frame["audit_window_end"] = str(end_date)[:10]
        frame["run_type"] = "MANUAL_FILE"
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

print("STEP 5 — Persist Gold audit evidence and reconciliation")
write_df(spark, result["detail"], "gold.audit_detail")
write_df(spark, result["event_adjustments"], "gold.audit_event_adjustments")
write_df(spark, result["toil_findings"], "gold.toil_findings")
write_df(spark, result["reconciliation"], "gold.pay_period_reconciliation")

print("STEP 6 — Record operational run counts")
reconciliation = result["reconciliation"]
actual_source = "FILES" if result["payroll_earnings"] is not None and not result["payroll_earnings"].empty else "NONE"
run = pd.DataFrame([{
    "audit_run_id": run_id,
    "run_type": "MANUAL_FILE",
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
    "message": f"manual input={input_root}",
}])
write_df(spark, run, "ops.audit_runs")
create_views(spark)

print("STEP 7 — Replace the BI-facing snapshot with this successful run")
# This occurs after calculation/persistence so a failed audit does not replace the
# previously successful Power BI snapshot.
publish_current_snapshots(spark, result)

print(f"Uploaded-file audit complete: {run_id}")
if not reconciliation.empty:
    print(reconciliation["status"].value_counts(dropna=False).to_string())
    display(reconciliation.sort_values(["status", "employee_name"]).head(200))
print("NEXT: review the AuditHero Power BI report.")
notebookutils.notebook.exit(run_id)
