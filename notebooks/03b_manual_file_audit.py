# Databricks notebook source
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1" "holidays>=0.75"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read())
from datetime import datetime, timezone
import uuid
import pandas as pd

from schads_audit.config import AuditConfig
from schads_audit.rules import RuleLibrary
from schads_audit.manual_audit import run_manual_audit
from schads_audit.databricks_io import write_df, create_views

dbutils.widgets.text('catalog','schads_payroll')
dbutils.widgets.text('input_root','')
dbutils.widgets.text('start_date','2023-07-01')
dbutils.widgets.text('end_date','2026-06-30')
catalog=dbutils.widgets.get('catalog')
input_root=dbutils.widgets.get('input_root') or f'/Volumes/{catalog}/bronze/landing/input'
start_date=dbutils.widgets.get('start_date'); end_date=dbutils.widgets.get('end_date')

run_id=str(uuid.uuid4()); started=datetime.now(timezone.utc)
lib=RuleLibrary(ROOT/'rules/MA000100')
result=run_manual_audit(input_root,ROOT/'config',start_date,end_date,lib)
finished=datetime.now(timezone.utc)

for df in (result['detail'],result['event_adjustments'],result['toil_findings'],result['reconciliation']):
    if df is not None and not df.empty:
        df['audit_run_id']=run_id; df['audit_window_start']=start_date; df['audit_window_end']=end_date
        df['run_type']='MANUAL_FILE'; df['run_finished_at']=finished

for name,df in (
    ('employees',result['employees']),('pay_details',result['pay_details']),
    ('employment_history',result['employment_history']),('timesheets',result['timesheets']),
    ('rostered_shifts',result['rostered_shifts']),('payroll_earnings',result['payroll_earnings']),
    ('public_holidays',result['public_holidays']),
):
    if df is not None and not df.empty:
        x=df.copy(); x['audit_run_id']=run_id; x['ingested_at']=finished
        write_df(spark,x,f'{catalog}.silver.{name}','append')

write_df(spark,result['detail'],f'{catalog}.gold.audit_detail','append')
write_df(spark,result['event_adjustments'],f'{catalog}.gold.audit_event_adjustments','append')
write_df(spark,result['toil_findings'],f'{catalog}.gold.toil_findings','append')
write_df(spark,result['reconciliation'],f'{catalog}.gold.pay_period_reconciliation','append')
recon=result['reconciliation']; actual='FILES' if not result['payroll_earnings'].empty else 'NONE'
run=pd.DataFrame([{
    'audit_run_id':run_id,'run_type':'MANUAL_FILE','audit_window_start':start_date,'audit_window_end':end_date,
    'started_at':started,'finished_at':finished,'status':'SUCCESS','actual_pay_source':actual,
    'employees':len(result['employees']),'timesheets':len(result['timesheets']),
    'underpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='UNDERPAID').sum()),
    'overpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='OVERPAID').sum()),
    'review_periods':int((recon.get('status',pd.Series(dtype=str))=='REQUIRES_REVIEW').sum()),
    'message':f'manual input={input_root}'
}])
write_df(spark,run,f'{catalog}.ops.audit_runs','append'); create_views(spark,catalog)
print(f'Manual file audit complete: {run_id}')
print(f'Input: {input_root}')
if not recon.empty:
    print(recon['status'].value_counts(dropna=False).to_string())
    display(recon.sort_values(['status','employee_name']).head(200))
