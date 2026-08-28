# Databricks notebook source
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read())
import pandas as pd
from schads_audit.file_readiness import assess_file_readiness
from schads_audit.databricks_io import write_df

dbutils.widgets.text('catalog','schads_payroll')
dbutils.widgets.text('input_root','')
catalog=dbutils.widgets.get('catalog')
input_root=dbutils.widgets.get('input_root') or f'/Volumes/{catalog}/bronze/landing/input'
findings=assess_file_readiness(input_root,ROOT/'config')
findings['checked_at']=pd.Timestamp.utcnow()
write_df(spark,findings,f'{catalog}.ops.readiness_findings','overwrite')
display(findings.sort_values(['status','finding_type','source_key']))
blocking=findings[findings.status=='BLOCKING']
print('\nFILE AUDIT READINESS SUMMARY')
print(findings.status.value_counts().to_string())
if len(blocking):
    raise ValueError(f'{len(blocking)} blocking file-readiness finding(s); resolve before remediation audit')
print('\nUploaded files are structurally ready. Validate one known pay period next.')
