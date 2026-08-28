from pathlib import Path
from datetime import datetime,timezone
import json,uuid,pandas as pd
from .employment_hero_hr import EmploymentHeroHRClient
from .employment_hero_payroll import EmploymentHeroPayrollClient
from .normalize import *
from .public_holidays import australian_public_holidays
from .engine import calculate_entitlements,reconcile_pay_periods
from .databricks_io import write_df

def _secret(dbutils,scope,key,required=True):
    try:return dbutils.secrets.get(scope=scope,key=key)
    except Exception:
        if required:raise
        return None
def load_json(path,default=None):
    p=Path(path);return json.loads(p.read_text()) if p.exists() else (default if default is not None else {})
def run_databricks_audit(spark,dbutils,config,lib,start_date,end_date,mapping_dir,run_type='HISTORICAL',actual_pay_source=None):
    run_id=str(uuid.uuid4());started=datetime.now(timezone.utc);source=(actual_pay_source or config.actual_pay_source).upper();mapping_dir=Path(mapping_dir)
    try:
        org=_secret(dbutils,config.secret_scope,'EH_ORGANISATION_ID');hr=EmploymentHeroHRClient(_secret(dbutils,config.secret_scope,'EH_HR_CLIENT_ID'),_secret(dbutils,config.secret_scope,'EH_HR_CLIENT_SECRET'),_secret(dbutils,config.secret_scope,'EH_HR_REFRESH_TOKEN'),config.hr_base_url,config.hr_token_url)
        employees_raw=hr.employees(org);ids=[str(x.get('id')) for x in employees_raw if x.get('id')];pay_raw,emp_hist_raw=hr.all_employee_histories(org,ids);ts_raw=hr.timesheets_chunked(org,start_date,end_date)
        employees=apply_employee_overrides(normalize_employees(employees_raw),load_json(mapping_dir/'employee_overrides.json',{}));pay_details=apply_classification_mapping(normalize_pay_details(pay_raw),load_json(mapping_dir/'classification_mapping.json',{}));emp_hist=normalize_employment_history(emp_hist_raw);timesheets=normalize_timesheets(ts_raw);timesheets['work_group']='DISABILITY_SERVICES';timesheets['location_state']=None
        payroll=pd.DataFrame();pay_runs=[]
        if source=='PAYROLL_API':
            key=_secret(dbutils,config.secret_scope,'EH_PAYROLL_API_KEY',False);bid=_secret(dbutils,config.secret_scope,'EH_PAYROLL_BUSINESS_ID',False)
            if key and bid:
                pc=EmploymentHeroPayrollClient(key,bid,config.payroll_base_url);pay_runs,raw=pc.pull_earnings(start_date,end_date);payroll=normalize_payroll_earnings(raw)
            else:source='NONE'
        holidays=pd.DataFrame(australian_public_holidays(start_date,end_date));detail=calculate_entitlements(employees,emp_hist,pay_details,timesheets,holidays,lib);recon=reconcile_pay_periods(detail,payroll,load_json(mapping_dir/'pay_category_mapping.json',{}),config.variance_tolerance)
        finished=datetime.now(timezone.utc)
        for df in (detail,recon):
            if not df.empty:df['audit_run_id']=run_id;df['audit_window_start']=str(start_date)[:10];df['audit_window_end']=str(end_date)[:10];df['run_type']=run_type;df['run_finished_at']=finished
        write_df(spark,detail,f'{config.catalog}.gold.audit_detail');write_df(spark,recon,f'{config.catalog}.gold.pay_period_reconciliation')
        run=pd.DataFrame([{'audit_run_id':run_id,'run_type':run_type,'audit_window_start':str(start_date)[:10],'audit_window_end':str(end_date)[:10],'started_at':started,'finished_at':finished,'status':'SUCCESS','actual_pay_source':source,'employees':len(employees),'timesheets':len(timesheets),'underpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='UNDERPAID').sum()),'overpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='OVERPAID').sum()),'review_periods':int((recon.get('status',pd.Series(dtype=str))=='REQUIRES_REVIEW').sum()),'message':''}]);write_df(spark,run,f'{config.catalog}.ops.audit_runs');return {'run_id':run_id,'detail':detail,'reconciliation':recon}
    except Exception as exc:
        finished=datetime.now(timezone.utc);write_df(spark,pd.DataFrame([{'audit_run_id':run_id,'run_type':run_type,'audit_window_start':str(start_date)[:10],'audit_window_end':str(end_date)[:10],'started_at':started,'finished_at':finished,'status':'FAILED','actual_pay_source':source,'employees':0,'timesheets':0,'underpaid_periods':0,'overpaid_periods':0,'review_periods':0,'message':f'{type(exc).__name__}: {exc}'}]),f'{config.catalog}.ops.audit_runs');raise
