# AuditHero — Monthly Payroll Audit (Optional API)
#
# PURPOSE
# -------
# Run the optional recurring Employment Hero API audit over a rolling lookback
# window. The schedule should remain disabled until a known period has been
# validated. File-based organisations can instead upload/convert current exports
# and run the Uploaded Files Audit Pipeline on their chosen cadence.
#
# PARAMETERS: key_vault_url, lookback_days, actual_pay_source

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.fabric_pipeline import run_fabric_audit
from schads_audit.fabric_bi_io import publish_current_snapshots

print("STEP 1 — Calculate the rolling audit window")
cfg = FabricAuditConfig(key_vault_url=key_vault_url, actual_pay_source=actual_pay_source)
today = datetime.now(ZoneInfo(cfg.timezone)).date()
end_date = today.isoformat()
start_date = (today - timedelta(days=int(lookback_days))).isoformat()
print(f"Audit window: {start_date} to {end_date}")

print("STEP 2 — Run the shared API audit engine")
lib = bundled_rule_library()
result = run_fabric_audit(
    spark,
    notebookutils,
    cfg,
    lib,
    start_date,
    end_date,
    run_type="MONTHLY",
    actual_pay_source=actual_pay_source,
)

print("STEP 3 — Publish current Direct Lake snapshot")
publish_current_snapshots(spark, result)
print(f"Monthly audit complete: {result['run_id']}")
if not result["reconciliation"].empty:
    print(result["reconciliation"]["status"].value_counts(dropna=False).to_string())
notebookutils.notebook.exit(result["run_id"])
