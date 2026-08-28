# Parameters: key_vault_url, lookback_days, actual_pay_source
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.fabric_pipeline import run_fabric_audit

cfg=FabricAuditConfig(key_vault_url=key_vault_url,actual_pay_source=actual_pay_source)
today=datetime.now(ZoneInfo(cfg.timezone)).date()
end_date=today.isoformat();start_date=(today-timedelta(days=int(lookback_days))).isoformat()
lib=bundled_rule_library()
result=run_fabric_audit(spark,notebookutils,cfg,lib,start_date,end_date,run_type='MONTHLY',actual_pay_source=actual_pay_source)
print(f"Monthly audit complete: {result['run_id']} ({start_date} to {end_date})")
if not result['reconciliation'].empty:
    print(result['reconciliation']['status'].value_counts(dropna=False).to_string())
notebookutils.notebook.exit(result['run_id'])
