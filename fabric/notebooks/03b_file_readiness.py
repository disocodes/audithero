# AuditHero — File Readiness
#
# PURPOSE
# -------
# Validate canonical uploaded files before they enter the payroll audit engine.
# This workflow requires no Employment Hero credentials and does not calculate pay.
#
# PARAMETER
# ---------
# input_root — folder containing audithero_input.xlsx or canonical files.

import pandas as pd
from schads_audit.file_readiness import assess_file_readiness
from schads_audit.fabric_io import write_df

print(f"STEP 1 — Inspect canonical input: {input_root}")
findings = assess_file_readiness(input_root, "/lakehouse/default/Files/config")
findings["checked_at"] = pd.Timestamp.utcnow()

print("STEP 2 — Save/display readiness findings")
write_df(spark, findings, "ops.readiness_findings", "overwrite")
display(findings.sort_values(["status", "finding_type", "source_key"]))

print("STEP 3 — Gate the downstream audit")
blocking = findings[findings.status == "BLOCKING"]
print("\nFILE AUDIT READINESS SUMMARY")
print(findings.status.value_counts().to_string())
if len(blocking):
    print(f"\n{len(blocking)} blocking finding(s). Correct the canonical data/evidence before running the audit.")
    notebookutils.notebook.exit("review_required")

print("\nUploaded files are structurally ready.")
print("Recommended next step: run one independently checked payroll period with the Uploaded Files Audit Pipeline.")
notebookutils.notebook.exit("success")
