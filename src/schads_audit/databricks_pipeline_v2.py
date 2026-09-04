from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid
import pandas as pd

from .employment_hero_hr import EmploymentHeroHRClient
from .employment_hero_payroll import EmploymentHeroPayrollClient
from .normalize import normalize_employees, normalize_pay_details, normalize_employment_history, normalize_timesheets, normalize_payroll_earnings, apply_classification_mapping, apply_employee_overrides
from .public_holidays import australian_public_holidays
from .engine import assign_pay_periods, calculate_entitlements, reconcile_pay_periods
from .roster_overtime import normalize_rosters, attach_rosters, apply_rostered_and_daily_overtime, allocate_period_overtime, flag_period_overtime
from .broken_sleepover import group_broken_shifts, apply_broken_shift_rules, group_sleepovers, apply_sleepover_group_rules
from .supplemental import calculate_supplemental_events, merge_event_adjustments_into_entitlements
from .remote_work import aggregate_remote_work_events
from .industrial_instruments import apply_instrument_history
from .part_time_patterns import apply_part_time_pattern_checks
from .rest_meal import apply_meal_break_events
from .rest_breaks import apply_rest_between_work
from .toil import audit_toil_register, merge_toil_adjustments
from .databricks_io import write_df, create_views


def _secret(dbutils, scope, key, required=True):
    try:return dbutils.secrets.get(scope=scope,key=key)
    except Exception:
        if required:raise
        return None


def load_json(path,default=None):
    p=Path(path)
    if not p.exists():return {} if default is None else default
    return json.loads(p.read_text(encoding='utf-8'))


def load_csv(path):
    p=Path(path)
    if not p.exists():return pd.DataFrame()
    try:return pd.read_csv(p)
    except pd.errors.EmptyDataError:return pd.DataFrame()


def _attach_timesheet_mappings(timesheets,work_type_mapping,location_mapping):
    """Attach only explicit configured work-type/location facts."""
    if timesheets.empty:return timesheets
    df=timesheets.copy();df['work_group']=None;df['is_sleepover']=False;df['location_state']=None;df['holiday_location_key']=None
    for idx,r in df.iterrows():
        for key in (str(r.get('work_type_id') or ''),str(r.get('work_type_name') or ''),str(r.get('position_name') or '')):
            if key in work_type_mapping:
                v=work_type_mapping[key]
                if isinstance(v,dict):
                    for field in ('work_group','is_sleepover','sleepover_12h_written_agreement','sleepover_group_id','broken_shift_breaks'):
                        if field in v:df.at[idx,field]=v[field]
                break
        for key in (str(r.get('work_site_id') or ''),str(r.get('location_id') or '')):
            if key in location_mapping:
                v=location_mapping[key]
                if isinstance(v,dict):df.at[idx,'location_state']=v.get('state');df.at[idx,'holiday_location_key']=v.get('holiday_location_key')
                else:df.at[idx,'location_state']=v
                break
    return df


def _append_holiday_overrides(holidays,mapping_dir):
    p=Path(mapping_dir)/'public_holiday_overrides.csv'
    if not p.exists():return holidays
    extra=load_csv(p)
    if extra.empty:return holidays
    out=pd.concat([holidays,extra],ignore_index=True,sort=False);cols=['state','holiday_date','holiday_name']
    if 'holiday_location_key' in out.columns:cols.append('holiday_location_key')
    return out.drop_duplicates(cols)


def _usable_api_payroll(payroll:pd.DataFrame,mapping:dict,employee_ids:set[str])->bool:
    required={'employee_id','pay_period_start','pay_period_end','pay_category','amount'}
    if payroll is None or payroll.empty or not mapping or not required.issubset(payroll.columns):return False
    blank=lambda s:s.isna()|s.astype(str).str.strip().str.lower().isin({'','nan','nat','none'})
    if any(blank(payroll[field]).any() for field in required):return False
    if pd.to_numeric(payroll['amount'],errors='coerce').isna().any():return False
    if not set(payroll['employee_id'].astype(str).str.strip()).issubset(employee_ids):return False
    for _,row in payroll.iterrows():
        found=False
        for key in (row.get('pay_category_id'),row.get('pay_category')):
            text='' if pd.isna(key) else str(key).strip()
            if text in mapping:
                value=mapping[text];t=value.get('audit_treatment') if isinstance(value,dict) else value
                if str(t or '').upper() in {'AUDITABLE_WORK','ALLOWANCE','EXCLUDE'}:found=True;break
        if not found:return False
    return True


def run_databricks_audit_v2(spark,dbutils,config,rule_library,start_date,end_date,mapping_dir,run_type='HISTORICAL',actual_pay_source=None):
    """Complete Databricks execution path; mirrors the Fabric pipeline module order."""
    run_id=str(uuid.uuid4());started=datetime.now(timezone.utc);source=(actual_pay_source or config.actual_pay_source).upper();root=Path(mapping_dir)
    try:
        org=_secret(dbutils,config.secret_scope,'EH_ORGANISATION_ID')
        hr=EmploymentHeroHRClient(_secret(dbutils,config.secret_scope,'EH_HR_CLIENT_ID'),_secret(dbutils,config.secret_scope,'EH_HR_CLIENT_SECRET'),_secret(dbutils,config.secret_scope,'EH_HR_REFRESH_TOKEN'),config.hr_base_url,config.hr_token_url)
        employees_raw=hr.employees(org);employee_ids=[str(x.get('id')) for x in employees_raw if x.get('id')];pay_raw,employment_raw=hr.all_employee_histories(org,employee_ids);timesheets_raw=hr.timesheets_chunked(org,start_date,end_date);rosters_raw=hr.rostered_shifts_chunked(org,start_date,end_date)
        employees=apply_employee_overrides(normalize_employees(employees_raw),load_json(root/'employee_overrides.json',{}));pay_details=apply_classification_mapping(normalize_pay_details(pay_raw),load_json(root/'classification_mapping.json',{}));employment_history=normalize_employment_history(employment_raw);rosters=normalize_rosters(rosters_raw)
        timesheets=_attach_timesheet_mappings(normalize_timesheets(timesheets_raw),load_json(root/'work_type_mapping.json',{}),load_json(root/'work_location_state_mapping.json',{}));timesheets=attach_rosters(timesheets,rosters);timesheets=group_sleepovers(timesheets);timesheets=group_broken_shifts(timesheets)

        payroll=pd.DataFrame();pay_runs=[]
        if source=='PAYROLL_API':
            api_key=_secret(dbutils,config.secret_scope,'EH_PAYROLL_API_KEY',False);business_id=_secret(dbutils,config.secret_scope,'EH_PAYROLL_BUSINESS_ID',False)
            if api_key and business_id:
                pc=EmploymentHeroPayrollClient(api_key,business_id,config.payroll_base_url);pay_runs,payroll_raw=pc.pull_earnings(start_date,end_date);payroll=normalize_payroll_earnings(payroll_raw);timesheets=assign_pay_periods(timesheets,pay_runs)
            else:source='NONE'

        holidays=pd.DataFrame(australian_public_holidays(start_date,end_date));holidays=_append_holiday_overrides(holidays,root)
        detail=calculate_entitlements(employees,employment_history,pay_details,timesheets,holidays,rule_library);detail=apply_broken_shift_rules(detail,timesheets,rule_library);detail=apply_sleepover_group_rules(detail,timesheets,rule_library);detail=apply_rostered_and_daily_overtime(detail,timesheets,holidays,rule_library);detail=allocate_period_overtime(detail,holidays,rule_library);detail=flag_period_overtime(detail);detail=apply_part_time_pattern_checks(detail,load_csv(root/'part_time_patterns.csv'),load_csv(root/'part_time_variations.csv'));detail=apply_meal_break_events(detail,timesheets,load_csv(root/'meal_break_events.csv'),holidays,rule_library)
        detail,rest_findings=apply_rest_between_work(detail,timesheets,rosters,load_csv(root/'rest_break_controls.csv'),load_csv(root/'overtime_rest_controls.csv'),rule_library);detail=apply_instrument_history(detail,load_csv(root/'industrial_instrument_history.csv'))
        events=aggregate_remote_work_events(load_csv(root/'supplemental_events.csv'));adjustments=calculate_supplemental_events(events,employees,pay_details,holidays,rule_library);recon_input=merge_event_adjustments_into_entitlements(detail,adjustments);toil=audit_toil_register(load_csv(root/'toil_register.csv'),employees,pay_details,holidays,rule_library,audit_end_date=end_date);recon_input=merge_toil_adjustments(recon_input,toil)
        pay_mapping=load_json(root/'pay_category_mapping.json',{});known_ids=set(employees.get('employee_id',pd.Series(dtype=object)).dropna().astype(str).str.strip());actual_pay_usable=_usable_api_payroll(payroll,pay_mapping,known_ids)
        if source=='PAYROLL_API' and not actual_pay_usable:source='PAYROLL_API_UNAVAILABLE'
        reconciliation=reconcile_pay_periods(recon_input,payroll if actual_pay_usable else pd.DataFrame(),pay_mapping if actual_pay_usable else {},config.variance_tolerance)

        finished=datetime.now(timezone.utc)
        for df in (detail,rest_findings,adjustments,toil,reconciliation):
            if df is not None and not df.empty:df['audit_run_id']=run_id;df['audit_window_start']=str(start_date)[:10];df['audit_window_end']=str(end_date)[:10];df['run_type']=run_type;df['run_finished_at']=finished
        for name,df in (('employees',employees),('pay_details',pay_details),('employment_history',employment_history),('timesheets',timesheets),('rostered_shifts',rosters),('payroll_earnings',payroll),('public_holidays',holidays)):
            if df is not None and not df.empty:
                x=df.copy();x['audit_run_id']=run_id;x['ingested_at']=finished;write_df(spark,x,f'{config.catalog}.silver.{name}','append')
        write_df(spark,detail,f'{config.catalog}.gold.audit_detail','append');write_df(spark,rest_findings,f'{config.catalog}.gold.rest_break_findings','append');write_df(spark,adjustments,f'{config.catalog}.gold.audit_event_adjustments','append');write_df(spark,toil,f'{config.catalog}.gold.toil_findings','append');write_df(spark,reconciliation,f'{config.catalog}.gold.pay_period_reconciliation','append')
        run=pd.DataFrame([{'audit_run_id':run_id,'run_type':run_type,'audit_window_start':str(start_date)[:10],'audit_window_end':str(end_date)[:10],'started_at':started,'finished_at':finished,'status':'SUCCESS','actual_pay_source':source,'employees':len(employees),'timesheets':len(timesheets),'underpaid_periods':int((reconciliation.get('status',pd.Series(dtype=str))=='UNDERPAID').sum()),'overpaid_periods':int((reconciliation.get('status',pd.Series(dtype=str))=='OVERPAID').sum()),'review_periods':int((reconciliation.get('status',pd.Series(dtype=str))=='REQUIRES_REVIEW').sum()),'message':f'rosters={len(rosters)}; rest_findings={len(rest_findings)}; supplemental={len(adjustments)}; toil={len(toil)}'}])
        write_df(spark,run,f'{config.catalog}.ops.audit_runs','append');create_views(spark,config.catalog);return {'run_id':run_id,'detail':detail,'rest_break_findings':rest_findings,'event_adjustments':adjustments,'toil_findings':toil,'reconciliation':reconciliation,'run':run}
    except Exception as exc:
        finished=datetime.now(timezone.utc);failure=pd.DataFrame([{'audit_run_id':run_id,'run_type':run_type,'audit_window_start':str(start_date)[:10],'audit_window_end':str(end_date)[:10],'started_at':started,'finished_at':finished,'status':'FAILED','actual_pay_source':source,'employees':0,'timesheets':0,'underpaid_periods':0,'overpaid_periods':0,'review_periods':0,'message':f'{type(exc).__name__}: {exc}'}]);write_df(spark,failure,f'{config.catalog}.ops.audit_runs','append');raise
