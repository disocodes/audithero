# Parameters: key_vault_url, start_date, end_date, actual_pay_source
from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.fabric_pipeline import run_fabric_audit
from schads_audit.fabric_bi_io import publish_current_snapshots

cfg=FabricAuditConfig(key_vault_url=key_vault_url,actual_pay_source=actual_pay_source)
lib=bundled_rule_library()
result=run_fabric_audit(spark,notebookutils,cfg,lib,start_date,end_date,run_type='HISTORICAL',actual_pay_source=actual_pay_source)
publish_current_snapshots(spark,result)
print(f"Historical audit complete: {result['run_id']}")
print("Direct Lake snapshot tables now represent this successful audit run.")
if not result['reconciliation'].empty:
    print(result['reconciliation']['status'].value_counts(dropna=False).to_string())
    display(result['reconciliation'].sort_values(['status','employee_name']).head(200))
notebookutils.notebook.exit(result['run_id'])
