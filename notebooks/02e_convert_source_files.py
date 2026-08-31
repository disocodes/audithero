# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Convert Source Files to the Canonical Audit Format
# MAGIC
# MAGIC This notebook turns your organisation's payroll/HR/timekeeping exports into the standard files that every AuditHero audit uses. It is the bridge between arbitrary source column names and the shared SCHADS calculation engine.
# MAGIC
# MAGIC It does **not** change Award rules or calculate entitlements. It only reads the approved mapping workbook/JSON, converts fields, writes canonical CSV files and `audithero_input.xlsx`, and produces a conversion report for review.
# COMMAND ----------
# MAGIC %pip install "openpyxl>=3.1"
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Parameters and standard locations
# MAGIC
# MAGIC Run this from **Jobs & Pipelines** and override the paths if your files live elsewhere. The default paths keep raw exports separate from the converted AuditHero input files.
# COMMAND ----------
from pathlib import Path
import sys

ROOT = Path.cwd()
for candidate in (ROOT, *ROOT.parents):
    if (candidate / "src" / "schads_audit").exists():
        sys.path.insert(0, str(candidate / "src"))
        break

from schads_audit.mapping_workbook import load_mapping
from schads_audit.source_mapping import convert_source_files
from schads_audit.file_readiness import assess_file_readiness

# UI/job parameters.
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("source_root", "")
dbutils.widgets.text("mapping_path", "")
dbutils.widgets.text("output_root", "")
dbutils.widgets.dropdown("strict", "true", ["true", "false"])

catalog = dbutils.widgets.get("catalog")
source_root = dbutils.widgets.get("source_root").strip() or f"/Volumes/{catalog}/bronze/landing/import/raw"
mapping_path = dbutils.widgets.get("mapping_path").strip() or f"/Volumes/{catalog}/bronze/landing/import/source_mapping.xlsx"
output_root = dbutils.widgets.get("output_root").strip() or f"/Volumes/{catalog}/bronze/landing/input"
strict = dbutils.widgets.get("strict").lower() == "true"

print(f"Source exports:  {source_root}")
print(f"Mapping file:    {mapping_path}")
print(f"Canonical output:{output_root}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Load the field mapping you approved
# MAGIC
# MAGIC `source_mapping.xlsx` is designed for non-technical editing. The `field_mapping` sheet tells AuditHero which source file/sheet/column feeds each canonical field. The optional `value_mapping` sheet translates values such as `Permanent FT` to `FULL_TIME`.
# COMMAND ----------
mapping_file = Path(mapping_path)
if not mapping_file.exists():
    raise FileNotFoundError(
        f"Mapping file not found: {mapping_path}. Run 'AuditHero - Build Source Mapping Workbook' first, edit the draft and upload it as source_mapping.xlsx."
    )

mapping = load_mapping(mapping_file)
enabled = [name for name, cfg in mapping.get("datasets", {}).items() if cfg.get("enabled")]
print("Enabled canonical datasets:", ", ".join(enabled) or "NONE")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Convert the exports
# MAGIC
# MAGIC The converter applies only the safe operations defined by the mapping workbook: copy, coalesce, concatenate, combine date/time, use a constant/default, translate known values and convert basic data types. Arbitrary Python expressions are never executed from the workbook.
# MAGIC
# MAGIC Outputs include individual canonical CSV files, a canonical `audithero_input.xlsx`, `mapping_used.json`, and `conversion_report.csv` showing row counts and blanks in required fields.
# COMMAND ----------
result = convert_source_files(
    source_root=source_root,
    mapping=mapping,
    output_root=output_root,
    write_workbook=True,
    strict=strict,
)

display(result["report"])
print(f"Canonical workbook: {result['workbook']}")
if result["errors"]:
    print("Conversion completed with issues:")
    for issue in result["errors"]:
        print(" -", issue)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Run the same readiness checks used before an audit
# MAGIC
# MAGIC Conversion success only proves that columns were transformed. This next step checks whether the canonical data is sufficiently complete for an audit — for example, whether classifications, timesheet identifiers and required historical coverage evidence are present.
# COMMAND ----------
readiness = assess_file_readiness(output_root, output_root)
display(readiness)
blocking = readiness[readiness["status"] == "BLOCKING"] if not readiness.empty else readiness

if len(blocking):
    print(f"Converted files were created, but {len(blocking)} blocking readiness item(s) remain.")
    display(blocking)
    raise ValueError("Canonical conversion completed but File Readiness is BLOCKING. Correct the mapping/source data and rerun conversion.")

print("Source conversion and File Readiness completed successfully.")
print("NEXT: run 'AuditHero - Audit Uploaded CSV Excel' for the required audit dates.")
