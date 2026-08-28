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

def csv_has_rows(name):
    p=root/name
    if not p.exists(): return False
    try:
        return not pd.read_csv(p).empty
    except (pd.errors.EmptyDataError, Exception):
        return False

def secret(name):
    return notebookutils.credentials.getSecret(cfg.key_vault_url, name)

client=EmploymentHeroHRClient(secret(cfg.hr_client_id_secret),secret(cfg.hr_client_secret_secret),secret(cfg.hr_refresh_token_secret),cfg.hr_base_url,cfg.hr_token_url)
org=secret(cfg.organisation_secret)
cls_map=load_json('classification_mapping.json');pay_map=load_json('pay_category_mapping.json');work_map=load_json('work_type_mapping.json');loc_map=load_json('work_location_state_mapping.json')
findings=[]
def add(kind,key,label,status,detail=''):
    findings.append({'finding_type':kind,'source_key':str(key or ''),'source_label':str(label or ''),'status':status,'detail':detail})

employees=client.employees(org)
has_part_time=False
for emp in employees:
    eid=str(emp.get('id') or '')
    current_type=str(first(emp,'employment_type','employmentType',default='') or '').upper()
    if 'PART' in current_type: has_part_time=True
    for hist in client.employment_histories(org,eid):
        if 'PART' in str(first(hist,'employment_type','employmentType',default='') or '').upper():
            has_part_time=True
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
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName');v=loc_map.get(str(rid or ''));mapped=isinstance(v,dict) and bool(v.get('state'))
    if not mapped:
        add('WORK_LOCATION',rid,label,'MAPPING_REQUIRED','State is required for public-holiday auditing')
    else:
        key=v.get('holiday_location_key');detail=f"state={v.get('state')}"+(f"; holiday_location_key={key}" if key else '; no local holiday key configured')
        add('WORK_LOCATION',rid,label,'READY' if key else 'MAPPING_RECOMMENDED',detail)

# Instrument history is a genuine historical-audit gate: classification alone does not prove Award coverage.
add('CONTROL_REGISTER','industrial_instrument_history.csv','industrial_instrument_history.csv',
    'READY' if csv_has_rows('industrial_instrument_history.csv') else 'REGISTER_REQUIRED',
    'Record effective-dated Award / enterprise agreement / IFA coverage for the historical population.')

if has_part_time:
    add('CONTROL_REGISTER','part_time_patterns.csv','part_time_patterns.csv',
        'READY' if csv_has_rows('part_time_patterns.csv') else 'REGISTER_REQUIRED',
        'Part-time employment exists; load effective-dated written guaranteed-hours patterns.')
else:
    add('CONTROL_REGISTER','part_time_patterns.csv','part_time_patterns.csv',
        'READY' if csv_has_rows('part_time_patterns.csv') else 'NOT_APPLICABLE',
        'No part-time employment was found in Employment Hero history.')

for filename,detail in {
    'overtime_rest_controls.csv':'Populate when an employee is directed to resume before the required post-overtime rest period.',
    'meal_break_events.csv':'Populate worked-through/client-meal exceptions when applicable.',
    'toil_register.csv':'Populate written TOIL agreements when TOIL is used.',
    'supplemental_events.csv':'Populate recall, on-call, remote work, active sleepover work or other controlled events when applicable.',
}.items():
    add('CONTROL_REGISTER',filename,filename,
        'READY' if csv_has_rows(filename) else 'REGISTER_REVIEW',
        detail+' An empty register is acceptable only after confirming the event type was not applicable in the audit window.')

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
    print('\nBlocking mappings/registers are present. Review REGISTER_REVIEW and MAPPING_RECOMMENDED items, then validate one known pay period.')
    notebookutils.notebook.exit('success')
