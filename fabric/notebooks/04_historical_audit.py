# AuditHero — Historical SCHADS Audit (Optional API)
#
# PURPOSE
# -------
# Run a payroll audit for a selected date range using Employment Hero HR/Payroll
# API extraction. Uploaded-file audits use the same shared calculation engine
# without Employment Hero API credentials.
#
# PARAMETERS
# ----------
# key_vault_url       — Azure Key Vault for Employment Hero API secrets.
# start_date/end_date — audit and extraction window.
# actual_pay_source   — PAYROLL_API to reconcile actual earnings, otherwise NONE.

from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.fabric_pipeline import run_fabric_audit
from schads_audit.fabric_bi_io import publish_current_snapshots

print("STEP 1 — Build API configuration and load the SCHADS rule library")
cfg = FabricAuditConfig(key_vault_url=key_vault_url, actual_pay_source=actual_pay_source)
lib = bundled_rule_library()

print(f"STEP 2 — Run historical audit from {start_date} to {end_date}")
# The shared pipeline performs API extraction, normalization, entitlement
# calculation, evidence controls, reconciliation and audit persistence.
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

print("STEP 3 — Publish the successful audit snapshot for reporting")
publish_current_snapshots(spark, result)

print(f"Historical audit complete: {result['run_id']}")
if not result["reconciliation"].empty:
    print(result["reconciliation"]["status"].value_counts(dropna=False).to_string())
    display(result["reconciliation"].sort_values(["status", "employee_name"]).head(200))
print("Recommended next step: review exceptions and supporting evidence in the AuditHero Power BI report.")
notebookutils.notebook.exit(result["run_id"])
