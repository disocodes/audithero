# Parameters: input_root, start_date, end_date
from datetime import datetime, timezone
import uuid
import pandas as pd

from schads_audit.fabric_rules import bundled_rule_library
from schads_audit.manual_audit import run_manual_audit
from schads_audit.fabric_io import write_df, create_views
from schads_audit.fabric_bi_io import publish_current_snapshots

run_id=str(uuid.uuid4())
started=datetime.now(timezone.utc)
lib=bundled_rule_library()
result=run_manual_audit(
    input_root=input_root,
    config_root="/lakehouse/default/Files/config",
    start_date=start_date,
    end_date=end_date,
    rule_library=lib,
)
finished=datetime.now(timezone.utc)

for df in (result['detail'],result['event_adjustments'],result['toil_findings'],result['reconciliation']):
    if df is not None and not df.empty:
        df['audit_run_id']=run_id
        df['audit_window_start']=str(start_date)[:10]
        df['audit_window_end']=str(end_date)[:10]
        df['run_type']='MANUAL_FILE'
        df['run_finished_at']=finished

for name,df in (
    ('employees',result['employees']),('pay_details',result['pay_details']),
    ('employment_history',result['employment_history']),('timesheets',result['timesheets']),
    ('rostered_shifts',result['rostered_shifts']),('payroll_earnings',result['payroll_earnings']),
    ('public_holidays',result['public_holidays']),
):
    if df is not None and not df.empty:
        x=df.copy(); x['audit_run_id']=run_id; x['ingested_at']=finished
        write_df(spark,x,f'silver.{name}')

write_df(spark,result['detail'],'gold.audit_detail')
write_df(spark,result['event_adjustments'],'gold.audit_event_adjustments')
write_df(spark,result['toil_findings'],'gold.toil_findings')
write_df(spark,result['reconciliation'],'gold.pay_period_reconciliation')

recon=result['reconciliation']
actual_source='FILES' if result['payroll_earnings'] is not None and not result['payroll_earnings'].empty else 'NONE'
run=pd.DataFrame([{
    'audit_run_id':run_id,'run_type':'MANUAL_FILE','audit_window_start':str(start_date)[:10],
    'audit_window_end':str(end_date)[:10],'started_at':started,'finished_at':finished,
    'status':'SUCCESS','actual_pay_source':actual_source,'employees':len(result['employees']),
    'timesheets':len(result['timesheets']),
    'underpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='UNDERPAID').sum()),
    'overpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='OVERPAID').sum()),
    'review_periods':int((recon.get('status',pd.Series(dtype=str))=='REQUIRES_REVIEW').sum()),
    'message':f'manual input={input_root}'
}])
write_df(spark,run,'ops.audit_runs')
create_views(spark)
publish_current_snapshots(spark,result)

print(f'Manual file audit complete: {run_id}')
print(f'Input: {input_root}')
if not recon.empty:
    print(recon['status'].value_counts(dropna=False).to_string())
    display(recon.sort_values(['status','employee_name']).head(200))
notebookutils.notebook.exit(run_id)
