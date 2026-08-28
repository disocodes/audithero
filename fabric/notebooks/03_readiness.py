# Parameters: key_vault_url
from pathlib import Path
import json
import pandas as pd

from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient
from schads_audit.normalize import infer_schads_classification, first
from schads_audit.fabric_io import write_df

cfg = FabricAuditConfig(key_vault_url=key_vault_url)
root = Path(cfg.config_root)

def load_json(name):
    p=root/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}

def secret(name):
    return notebookutils.credentials.getSecret(cfg.key_vault_url, name)

client=EmploymentHeroHRClient(secret(cfg.hr_client_id_secret),secret(cfg.hr_client_secret_secret),secret(cfg.hr_refresh_token_secret),cfg.hr_base_url,cfg.hr_token_url)
org=secret(cfg.organisation_secret)
cls_map=load_json('classification_mapping.json');pay_map=load_json('pay_category_mapping.json');work_map=load_json('work_type_mapping.json');loc_map=load_json('work_location_state_mapping.json')
findings=[]
def add(kind,key,label,status,detail=''):
    findings.append({'finding_type':kind,'source_key':str(key or ''),'source_label':str(label or ''),'status':status,'detail':detail})

employees=client.employees(org)
for emp in employees:
    eid=str(emp.get('id') or '')
    for row in client.pay_details(org,eid):
        label=first(row,'classification','classification_name','classificationName');rid=first(row,'id','Id');resolved=None
        for k in (str(rid or ''),str(label or '')):
            if k in cls_map:
                v=cls_map[k];resolved=v.get('classification_code') if isinstance(v,dict) else v;break
        resolved=resolved or infer_schads_classification(label)
        add('CLASSIFICATION',rid,label,'READY' if resolved else 'MAPPING_REQUIRED',resolved or 'No canonical SCHADS classification resolved')
for row in client.pay_categories(org):
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName','pay_category_name','payCategoryName');mapped=any(k in pay_map for k in (str(rid or ''),str(label or '')));add('PAY_CATEGORY',rid,label,'READY' if mapped else 'MAPPING_REQUIRED','Map to AUDITABLE_WORK, ALLOWANCE or EXCLUDE')
for row in client.work_types(org):
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName');mapped=any(k in work_map for k in (str(rid or ''),str(label or '')));add('WORK_TYPE',rid,label,'READY' if mapped else 'MAPPING_RECOMMENDED','Needed for work-group and sleepover automation')
for row in client.work_locations(org):
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName');v=loc_map.get(str(rid or ''));mapped=v is not None;detail='State and optional local holiday key available' if mapped else 'State is required for public-holiday auditing';add('WORK_LOCATION',rid,label,'READY' if mapped else 'MAPPING_REQUIRED',detail)

required_registers={
 'industrial_instrument_history.csv':'Historical Award/EA/IFA coverage register',
 'part_time_patterns.csv':'Effective-dated written part-time pattern register',
 'overtime_rest_controls.csv':'Evidence register for instructed return before 10-hour rest where applicable',
 'meal_break_events.csv':'Controlled worked-through/client-meal events where applicable',
 'toil_register.csv':'Written TOIL agreements where used',
}
for filename,detail in required_registers.items():
    p=root/filename
    status='READY' if p.exists() and p.stat().st_size>20 else 'REGISTER_REQUIRED'
    add('CONTROL_REGISTER',filename,filename,status,detail)

out=pd.DataFrame(findings).drop_duplicates(['finding_type','source_key','source_label'])
out['checked_at']=pd.Timestamp.utcnow()
write_df(spark,out,'ops.readiness_findings','overwrite')
display(out.sort_values(['status','finding_type','source_label']))
blocking=out[out.status.isin(['MAPPING_REQUIRED','REGISTER_REQUIRED'])]
print('\nAUDIT READINESS SUMMARY')
print(out.status.value_counts().to_string())
if len(blocking):
    print(f'\n{len(blocking)} blocking readiness findings. Resolve these before relying on historical remediation totals.')
    notebookutils.notebook.exit('review_required')
else:
    print('\nRequired mappings/registers are present. Validate one pay period next.')
    notebookutils.notebook.exit('success')
