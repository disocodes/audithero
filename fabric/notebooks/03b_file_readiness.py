# Parameters: input_root
from pathlib import Path
import pandas as pd
from schads_audit.file_readiness import assess_file_readiness
from schads_audit.fabric_io import write_df

findings=assess_file_readiness(input_root,"/lakehouse/default/Files/config")
findings['checked_at']=pd.Timestamp.utcnow()
write_df(spark,findings,'ops.readiness_findings','overwrite')
display(findings.sort_values(['status','finding_type','source_key']))
blocking=findings[findings.status=='BLOCKING']
print('\nFILE AUDIT READINESS SUMMARY')
print(findings.status.value_counts().to_string())
if len(blocking):
    print(f'\n{len(blocking)} blocking finding(s). Resolve them before relying on remediation totals.')
    notebookutils.notebook.exit('review_required')
print('\nUploaded files are structurally ready. Validate one known pay period next.')
notebookutils.notebook.exit('success')
