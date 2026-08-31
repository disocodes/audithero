# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — File Readiness
# MAGIC
# MAGIC **Purpose:** validate the canonical uploaded workbook/CSV files before an audit. This is the readiness workflow for FILES mode and does not require Employment Hero credentials.
# MAGIC
# MAGIC It checks required datasets/columns, classification completeness, pay-period evidence, historical instrument coverage, part-time pattern evidence and actual-pay/pay-category requirements. It does not calculate entitlements.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1"
# COMMAND ----------
exec(open(str(Path.cwd() / "_common.py")).read())

import pandas as pd
from schads_audit.file_readiness import assess_file_readiness
from schads_audit.databricks_io import write_df
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Select the canonical input folder
# MAGIC
# MAGIC If `input_root` is blank, AuditHero uses the standard Unity Catalog Volume folder created for canonical input files.
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("input_root", "")
catalog = dbutils.widgets.get("catalog")
input_root = dbutils.widgets.get("input_root").strip() or f"/Volumes/{catalog}/bronze/landing/input"
print(f"Checking canonical files under: {input_root}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run structural/evidence readiness checks
# MAGIC
# MAGIC Findings marked `BLOCKING` stop the downstream audit job. `REVIEW` findings mean an operator should understand the limitation before using the result.
# COMMAND ----------
findings = assess_file_readiness(input_root, ROOT / "config")
findings["checked_at"] = pd.Timestamp.utcnow()
write_df(spark, findings, f"{catalog}.ops.readiness_findings", "overwrite")
display(findings.sort_values(["status", "finding_type", "source_key"]))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Gate the audit
# MAGIC
# MAGIC A successful notebook means the uploaded canonical files are structurally ready to enter the audit engine. It does not mean every payroll conclusion is already remediation-ready; `REQUIRES_REVIEW` can still arise from shift-level evidence during calculation.
# COMMAND ----------
blocking = findings[findings.status == "BLOCKING"]
print("\nFILE AUDIT READINESS SUMMARY")
print(findings.status.value_counts().to_string())
if len(blocking):
    raise ValueError(f"{len(blocking)} blocking file-readiness finding(s); resolve them before running the audit")

print("\nUploaded files are structurally ready.")
print("NEXT: run one known payroll period with 'AuditHero - Audit Uploaded CSV Excel'.")
