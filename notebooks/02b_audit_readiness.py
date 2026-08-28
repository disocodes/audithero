# Databricks notebook source
# MAGIC %pip install "requests>=2.32" "pandas>=2.0"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read())
import json,pandas as pd
from schads_audit.config import AuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient
from schads_audit.normalize import infer_schads_classification,first
from schads_audit.databricks_io import write_df

dbutils.widgets.text('catalog','schads_payroll');dbutils.widgets.text('secret_scope','audithero')
catalog=dbutils.widgets.get('catalog');scope=dbutils.widgets.get('secret_scope');cfg=AuditConfig(catalog=catalog,secret_scope=scope)
secret=lambda k:dbutils.secrets.get(scope=scope,key=k)
client=EmploymentHeroHRClient(secret('EH_HR_CLIENT_ID'),secret('EH_HR_CLIENT_SECRET'),secret('EH_HR_REFRESH_TOKEN'),cfg.hr_base_url,cfg.hr_token_url);org=secret('EH_ORGANISATION_ID')

def load(name):
    p=ROOT/'config'/name
    return json.loads(p.read_text()) if p.exists() else {}
cls_map=load('classification_mapping.json');pay_map=load('pay_category_mapping.json');work_map=load('work_type_mapping.json');loc_map=load('work_location_state_mapping.json')
findings=[]
def add(kind,key,label,status,detail=''):
    findings.append({'finding_type':kind,'source_key':str(key or ''),'source_label':str(label or ''),'status':status,'detail':detail})

employees=client.employees(org);employee_ids=[str(x.get('id')) for x in employees if x.get('id')]
for eid in employee_ids:
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
    rid=first(row,'id','Id');label=first(row,'name','display_name','displayName');mapped=str(rid or '') in loc_map;add('WORK_LOCATION',rid,label,'READY' if mapped else 'MAPPING_REQUIRED','State is required for public-holiday auditing')

out=pd.DataFrame(findings).drop_duplicates(['finding_type','source_key','source_label']);out['checked_at']=pd.Timestamp.utcnow();write_df(spark,out,f'{catalog}.ops.readiness_findings','overwrite');display(out.sort_values(['status','finding_type','source_label']))
critical=out[out.status=='MAPPING_REQUIRED'];print('\nAUDIT READINESS SUMMARY');print(out.status.value_counts().to_string())
if len(critical):print(f'\nNEXT: resolve {len(critical)} required mappings before a remediation audit. See config/*.example files.')
else:print('\n✓ Required mappings are present. Run a one-month validation audit next.')
