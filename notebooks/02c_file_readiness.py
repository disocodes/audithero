# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — File Readiness
# MAGIC
# MAGIC **Purpose:** validate canonical uploaded workbook/CSV data before it enters the payroll audit workflow.
# MAGIC
# MAGIC File Readiness checks required datasets and columns, classification completeness, pay-period evidence, historical instrument coverage, part-time pattern evidence, and actual-pay/pay-category requirements. It does not calculate entitlements.
# MAGIC
# MAGIC **Credentials:** Employment Hero credentials are not required for this workflow.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

import pandas as pd
from schads_audit.file_readiness import assess_file_readiness
from schads_audit.databricks_io import write_df
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Select the canonical input folder
# MAGIC
# MAGIC If `input_root` is blank, AuditHero uses the standard Unity Catalog Volume folder created during Setup.
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("input_root", "")
catalog = dbutils.widgets.get("catalog")
input_root = dbutils.widgets.get("input_root").strip() or f"/Volumes/{catalog}/bronze/landing/input"
print(f"Checking canonical files under: {input_root}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run data and evidence readiness checks
# MAGIC
# MAGIC Findings marked `BLOCKING` stop the downstream audit Job. `REVIEW` findings identify limitations that require assessment during audit review.
# COMMAND ----------
findings = assess_file_readiness(input_root, ROOT / "config")
findings["checked_at"] = pd.Timestamp.utcnow()
write_df(spark, findings, f"{catalog}.ops.readiness_findings", "overwrite")
display(findings.sort_values(["status", "finding_type", "source_key"]))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Gate the audit
# MAGIC
# MAGIC A successful File Readiness result confirms that the canonical input can enter the audit engine. Shift-level evidence can still produce `REQUIRES_REVIEW` during entitlement calculation.
# COMMAND ----------
blocking = findings[findings.status == "BLOCKING"]
print("\nFILE AUDIT READINESS SUMMARY")
print(findings.status.value_counts().to_string())
if len(blocking):
    raise ValueError(f"{len(blocking)} blocking file-readiness finding(s); resolve them before running the audit")

print("\nUploaded files are ready for audit processing.")
print("Recommended next step: run 'AuditHero - Audit Uploaded CSV Excel' for the required audit dates.")
