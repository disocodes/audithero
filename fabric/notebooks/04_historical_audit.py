# AuditHero — Historical SCHADS Audit (Optional API)
#
# PURPOSE
# -------
# Run a date-range audit after extracting Employment Hero HR/Payroll data through
# optional API mode. Uploaded-file audits use the same shared calculation engine
# without API credentials.
#
# PARAMETERS
# key_vault_url     — Azure Key Vault for Employment Hero API secrets.
# start_date/end_date — audit/extraction window.
# actual_pay_source — PAYROLL_API to reconcile actual earnings, otherwise NONE.

from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.fabric_pipeline import run_fabric_audit
from schads_audit.fabric_bi_io import publish_current_snapshots

print("STEP 1 — Build Fabric/API configuration and load the shared rule library")
cfg = FabricAuditConfig(key_vault_url=key_vault_url, actual_pay_source=actual_pay_source)
lib = bundled_rule_library()

print(f"STEP 2 — Run historical audit from {start_date} to {end_date}")
# The shared pipeline performs API extraction, normalization, Award calculation,
# evidence controls and reconciliation. The formulas are not duplicated here.
result = run_fabric_audit(
    spark,
    notebookutils,
    cfg,
    lib,
    start_date,
    end_date,
    run_type="HISTORICAL",
    actual_pay_source=actual_pay_source,
)

print("STEP 3 — Publish BI snapshot only after successful audit completion")
publish_current_snapshots(spark, result)

print(f"Historical audit complete: {result['run_id']}")
if not result["reconciliation"].empty:
    print(result["reconciliation"]["status"].value_counts(dropna=False).to_string())
    display(result["reconciliation"].sort_values(["status", "employee_name"]).head(200))
print("NEXT: review exceptions and supporting evidence in the AuditHero Power BI report.")
notebookutils.notebook.exit(result["run_id"])
