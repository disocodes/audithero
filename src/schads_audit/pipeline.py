from pathlib import Path
from datetime import datetime,timezone
import json,uuid,pandas as pd

from .employment_hero_hr import EmploymentHeroHRClient
from .employment_hero_payroll import EmploymentHeroPayrollClient
from .normalize import normalize_employees,normalize_pay_details,normalize_employment_history,normalize_timesheets,normalize_payroll_earnings,apply_classification_mapping,apply_employee_overrides
from .public_holidays import australian_public_holidays
from .engine import assign_pay_periods,calculate_entitlements,reconcile_pay_periods
from .roster_overtime import normalize_rosters,attach_rosters,apply_rostered_and_daily_overtime,flag_period_overtime
from .supplemental import calculate_supplemental_events,merge_event_adjustments_into_entitlements
from .databricks_io import write_df


def _secret(dbutils,scope,key,required=True):
    try:return dbutils.secrets.get(scope=scope,key=key)
    except Exception:
        if required:raise
        return None

def load_json(path,default=None):
    p=Path(path);return json.loads(p.read_text()) if p.exists() else (default if default is not None else {})

def _apply_timesheet_mappings(df,work_types,locations):
    out=df.copy();out['work_group']='DISABILITY_SERVICES';out['is_sleepover']=False;out['location_state']=None
    for i,r in out.iterrows():
        for k in [str(r.get('work_type_id') or ''),str(r.get('work_type_name') or ''),str(r.get('position_name') or '')]:
            if k in work_types:
                v=work_types[k]
                if isinstance(v,dict):
                    for f in ('work_group','is_sleepover','sleepover_12h_written_agreement','sleepover_group_id','broken_shift_breaks'):
                        if f in v:out.at[i,f]=v[f]
                break
        for k in [str(r.get('work_site_id') or ''),str(r.get('location_id') or '')]:
            if k in locations:
                v=locations[k];out.at[i,'location_state']=v.get('state') if isinstance(v,dict) else v;break
    return out

def _load_supplemental_events(spark,catalog):
    path=f'/Volumes/{catalog}/bronze/landing/supplemental_events.csv'
    try:return spark.read.option('header',True).option('inferSchema',True).csv(path).toPandas()
    except Exception:return pd.DataFrame()

def _mark_cross_midnight_for_review(detail):
    if detail is None or detail.empty:return detail,pd.Series(dtype=bool)
    s=pd.to_datetime(detail['shift_start'],errors='coerce');e=pd.to_datetime(detail['shift_end'],errors='coerce');mask=s.dt.date!=e.dt.date
    for idx in detail.index[mask]:
        flags=[x for x in str(detail.at[idx,'review_flags'] or '').split('; ') if x];flags.append('CROSS_MIDNIGHT_OVERTIME_ALLOCATION_REVIEW');detail.at[idx,'review_flags']='; '.join(sorted(set(flags)));detail.at[idx,'entitlement_status']='REQUIRES_REVIEW'
    return detail,mask

def run_databricks_audit(spark,dbutils,config,lib,start_date,end_date,mapping_dir,run_type='HISTORICAL',actual_pay_source=None):
    run_id=str(uuid.uuid4());started=datetime.now(timezone.utc);source=(actual_pay_source or config.actual_pay_source).upper();mapping_dir=Path(mapping_dir)
    try:
        org=_secret(dbutils,config.secret_scope,'EH_ORGANISATION_ID');hr=EmploymentHeroHRClient(_secret(dbutils,config.secret_scope,'EH_HR_CLIENT_ID'),_secret(dbutils,config.secret_scope,'EH_HR_CLIENT_SECRET'),_secret(dbutils,config.secret_scope,'EH_HR_REFRESH_TOKEN'),config.hr_base_url,config.hr_token_url)
        employees_raw=hr.employees(org);ids=[str(x.get('id')) for x in employees_raw if x.get('id')];pay_raw,emp_hist_raw=hr.all_employee_histories(org,ids);ts_raw=hr.timesheets_chunked(org,start_date,end_date);roster_raw=hr.rostered_shifts_chunked(org,start_date,end_date)
        employees=apply_employee_overrides(normalize_employees(employees_raw),load_json(mapping_dir/'employee_overrides.json',{}));pay_details=apply_classification_mapping(normalize_pay_details(pay_raw),load_json(mapping_dir/'classification_mapping.json',{}));emp_hist=normalize_employment_history(emp_hist_raw);rosters=normalize_rosters(roster_raw)
        timesheets=_apply_timesheet_mappings(normalize_timesheets(ts_raw),load_json(mapping_dir/'work_type_mapping.json',{}),load_json(mapping_dir/'work_location_state_mapping.json',{}));timesheets=attach_rosters(timesheets,rosters)
        payroll=pd.DataFrame();pay_runs=[]
        if source=='PAYROLL_API':
            key=_secret(dbutils,config.secret_scope,'EH_PAYROLL_API_KEY',False);bid=_secret(dbutils,config.secret_scope,'EH_PAYROLL_BUSINESS_ID',False)
            if key and bid:
                pc=EmploymentHeroPayrollClient(key,bid,config.payroll_base_url);pay_runs,raw=pc.pull_earnings(start_date,end_date);payroll=normalize_payroll_earnings(raw);timesheets=assign_pay_periods(timesheets,pay_runs)
            else:source='NONE'
        holidays=pd.DataFrame(australian_public_holidays(start_date,end_date));override=mapping_dir/'public_holiday_overrides.csv'
        if override.exists():holidays=pd.concat([holidays,pd.read_csv(override)],ignore_index=True).drop_duplicates(['state','holiday_date'])
        detail=calculate_entitlements(employees,emp_hist,pay_details,timesheets,holidays,lib);detail,cross=_mark_cross_midnight_for_review(detail)
        if not detail.empty:
            safe=detail.loc[~cross].copy();safe_ts=timesheets[timesheets['timesheet_id'].astype(str).isin(safe['timesheet_id'].astype(str))];safe=apply_rostered_and_daily_overtime(safe,safe_ts,holidays,lib);detail=pd.concat([safe,detail.loc[cross]],ignore_index=True,sort=False);detail=flag_period_overtime(detail)
        events=_load_supplemental_events(spark,config.catalog);event_adjustments=calculate_supplemental_events(events,employees,pay_details,holidays,lib);recon_input=merge_event_adjustments_into_entitlements(detail,event_adjustments);recon=reconcile_pay_periods(recon_input,payroll,load_json(mapping_dir/'pay_category_mapping.json',{}),config.variance_tolerance)
        finished=datetime.now(timezone.utc)
        for df in (detail,event_adjustments,recon):
            if df is not None and not df.empty:df['audit_run_id']=run_id;df['audit_window_start']=str(start_date)[:10];df['audit_window_end']=str(end_date)[:10];df['run_type']=run_type;df['run_finished_at']=finished
        for name,df in [('employees',employees),('pay_details',pay_details),('employment_history',emp_hist),('timesheets',timesheets),('rostered_shifts',rosters),('payroll_earnings',payroll),('public_holidays',holidays)]:
            if df is not None and not df.empty:
                x=df.copy();x['audit_run_id']=run_id;x['ingested_at']=finished;write_df(spark,x,f'{config.catalog}.silver.{name}')
        write_df(spark,detail,f'{config.catalog}.gold.audit_detail');write_df(spark,event_adjustments,f'{config.catalog}.gold.audit_event_adjustments');write_df(spark,recon,f'{config.catalog}.gold.pay_period_reconciliation')
        run=pd.DataFrame([{'audit_run_id':run_id,'run_type':run_type,'audit_window_start':str(start_date)[:10],'audit_window_end':str(end_date)[:10],'started_at':started,'finished_at':finished,'status':'SUCCESS','actual_pay_source':source,'employees':len(employees),'timesheets':len(timesheets),'underpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='UNDERPAID').sum()),'overpaid_periods':int((recon.get('status',pd.Series(dtype=str))=='OVERPAID').sum()),'review_periods':int((recon.get('status',pd.Series(dtype=str))=='REQUIRES_REVIEW').sum()),'message':f'rosters={len(rosters)}; supplemental_events={len(event_adjustments)}'}]);write_df(spark,run,f'{config.catalog}.ops.audit_runs');return {'run_id':run_id,'detail':detail,'event_adjustments':event_adjustments,'reconciliation':recon}
    except Exception as exc:
        finished=datetime.now(timezone.utc);write_df(spark,pd.DataFrame([{'audit_run_id':run_id,'run_type':run_type,'audit_window_start':str(start_date)[:10],'audit_window_end':str(end_date)[:10],'started_at':started,'finished_at':finished,'status':'FAILED','actual_pay_source':source,'employees':0,'timesheets':0,'underpaid_periods':0,'overpaid_periods':0,'review_periods':0,'message':f'{type(exc).__name__}: {exc}'}]),f'{config.catalog}.ops.audit_runs');raise
