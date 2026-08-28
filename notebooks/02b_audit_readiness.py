# Databricks notebook source
# MAGIC %pip install "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read())
import json,pandas as pd
from schads_audit.config import AuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient
from schads_audit.normalize import infer_schads_classification,first
from schads_audit.databricks_io import write_df
from schads_audit.readiness import read_register,employee_register_coverage,coverage_detail

dbutils.widgets.text('catalog','schads_payroll');dbutils.widgets.text('secret_scope','audithero')
catalog=dbutils.widgets.get('catalog');scope=dbutils.widgets.get('secret_scope');cfg=AuditConfig(catalog=catalog,secret_scope=scope)
secret=lambda k:dbutils.secrets.get(scope=scope,key=k)
client=EmploymentHeroHRClient(secret('EH_HR_CLIENT_ID'),secret('EH_HR_CLIENT_SECRET'),secret('EH_HR_REFRESH_TOKEN'),cfg.hr_base_url,cfg.hr_token_url);org=secret('EH_ORGANISATION_ID')

def load(name):
    p=ROOT/'config'/name
    return json.loads(p.read_text()) if p.exists() else {}

def reg(name):
    return read_register(ROOT/'config'/name)

cls_map=load('classification_mapping.json');pay_map=load('pay_category_mapping.json');work_map=load('work_type_mapping.json');loc_map=load('work_location_state_mapping.json')
findings=[]
def add(kind,key,label,status,detail=''):
    findings.append({'finding_type':kind,'source_key':str(key or ''),'source_label':str(label or ''),'status':status,'detail':detail})

employees=client.employees(org);employee_ids=[str(x.get('id')) for x in employees if x.get('id')]
part_time_employee_ids=set()
for emp in employees:
    eid=str(emp.get('id') or '')
    if 'PART' in str(first(emp,'employment_type','employmentType',default='') or '').upper():
        part_time_employee_ids.add(eid)
for eid in employee_ids:
    for hist in client.employment_histories(org,eid):
        if 'PART' in str(first(hist,'employment_type','employmentType',default='') or '').upper():
            part_time_employee_ids.add(eid)
    for pdrow in client.pay_details(org,eid):
        label=first(pdrow,'classification','classification_name','classificationName');pid=first(pdrow,'id','Id');mapped=None
        for k in (str(pid or ''),str(label or '')):
            if k in cls_map:
                v=cls_map[k];mapped=v.get('classification_code') if isinstance(v,dict) else v;break
        mapped=mapped or infer_schads_classification(label)
        add('CLASSIFICATION',pid,label,'READY' if mapped else 'MAPPING_REQUIRED',mapped or 'No canonical SCHADS classification resolved')

for row in client.pay_categories(org):
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName','pay_category_name','payCategoryName');mapped=any(k in pay_map for k in (str(rid or ''),str(label or '')));add('PAY_CATEGORY',rid,label,'READY' if mapped else 'MAPPING_REQUIRED','Must map to AUDITABLE_WORK, ALLOWANCE or EXCLUDE')
for row in client.work_types(org):
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName');mapped=any(k in work_map for k in (str(rid or ''),str(label or '')));add('WORK_TYPE',rid,label,'READY' if mapped else 'MAPPING_RECOMMENDED','Needed for sleepover/work-group automation')
for row in client.work_locations(org):
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName');cfgrow=loc_map.get(str(rid or ''));mapped=isinstance(cfgrow,dict) and bool(cfgrow.get('state'))
    if not mapped:
        add('WORK_LOCATION',rid,label,'MAPPING_REQUIRED','State is required for public-holiday auditing')
    else:
        key=cfgrow.get('holiday_location_key');detail=f"state={cfgrow.get('state')}"+(f"; holiday_location_key={key}" if key else '; no local holiday key configured')
        add('WORK_LOCATION',rid,label,'READY' if key else 'MAPPING_RECOMMENDED',detail)

instrument_coverage=employee_register_coverage(reg('industrial_instrument_history.csv'),employee_ids)
add('CONTROL_REGISTER','industrial_instrument_history.csv','industrial_instrument_history.csv',
    'READY' if instrument_coverage['covered'] else 'REGISTER_REQUIRED',
    coverage_detail(instrument_coverage,'industrial-instrument history')+' Effective-date continuity is tested again at shift level.')

if part_time_employee_ids:
    pattern_coverage=employee_register_coverage(reg('part_time_patterns.csv'),part_time_employee_ids)
    add('CONTROL_REGISTER','part_time_patterns.csv','part_time_patterns.csv',
        'READY' if pattern_coverage['covered'] else 'REGISTER_REQUIRED',
        coverage_detail(pattern_coverage,'written part-time pattern')+' Effective-date applicability is tested again during the audit.')
else:
    add('CONTROL_REGISTER','part_time_patterns.csv','part_time_patterns.csv','NOT_APPLICABLE','No part-time employment was found in Employment Hero history.')

for filename,detail in {
    'overtime_rest_controls.csv':'Populate when an employee is directed to resume before the required post-overtime rest period.',
    'meal_break_events.csv':'Populate worked-through/client-meal exceptions when applicable.',
    'toil_register.csv':'Populate written TOIL agreements when TOIL is used.',
    'supplemental_events.csv':'Populate recall, on-call, remote work, active sleepover work or other controlled events when applicable.',
}.items():
    frame=reg(filename)
    add('CONTROL_REGISTER',filename,filename,
        'READY' if not frame.empty else 'REGISTER_REVIEW',
        detail+' An empty register is acceptable only after confirming the event type was not applicable in the audit window.')

out=pd.DataFrame(findings).drop_duplicates(['finding_type','source_key','source_label']);out['checked_at']=pd.Timestamp.utcnow();write_df(spark,out,f'{catalog}.ops.readiness_findings','overwrite');display(out.sort_values(['status','finding_type','source_label']))
blocking=out[out.status.isin(['MAPPING_REQUIRED','REGISTER_REQUIRED'])]
print('\nAUDIT READINESS SUMMARY');print(out.status.value_counts().to_string())
if len(blocking):
    print(f'\nNEXT: resolve {len(blocking)} blocking mappings/registers before relying on remediation totals.')
else:
    print('\nBlocking mappings/registers have employee-level coverage. Review REGISTER_REVIEW and MAPPING_RECOMMENDED items, then run a one-month validation audit.')
