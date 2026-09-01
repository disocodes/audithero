# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Convert Source Files
# MAGIC
# MAGIC **Purpose:** convert approved payroll, HR, rostering and timekeeping exports into the AuditHero canonical file format and run File Readiness.
# MAGIC
# MAGIC This notebook does not calculate SCHADS entitlements. Use it when conversion and readiness need to be reviewed before running the payroll audit.
# COMMAND ----------
# MAGIC %pip install "openpyxl>=3.1"
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Select the source, mapping and output locations
# MAGIC
# MAGIC The standard Job already supplies the AuditHero Unity Catalog Volume paths. Override a path only when the files are stored elsewhere.
# COMMAND ----------
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path.cwd()
for candidate in (ROOT, *ROOT.parents):
    if (candidate / "src" / "schads_audit").exists():
        sys.path.insert(0, str(candidate / "src"))
        break

from schads_audit.mapping_workbook import load_mapping
from schads_audit.source_mapping import convert_source_files
from schads_audit.file_readiness import assess_file_readiness

# Job parameters.
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
# MAGIC ## 2. Load the approved source mapping
# MAGIC
# MAGIC `source_mapping.xlsx` identifies the source file, sheet and field used for each AuditHero canonical field. The optional `value_mapping` sheet translates source values to approved canonical values.
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
# MAGIC ## 3. Convert the source files
# MAGIC
# MAGIC Supported mapping operations include direct copy, coalesce, concatenate, separate date/time combination, constants, defaults, value translation and basic data-type conversion. Mapping workbooks cannot execute arbitrary Python code.
# MAGIC
# MAGIC Outputs include canonical CSV files, `audithero_input.xlsx`, `mapping_used.json` and `conversion_report.csv`.
# COMMAND ----------
def _publish_staged_files(staging_root: Path, destination_root: str) -> None:
    """Copy completed conversion files into a Unity Catalog Volume."""
    target_root = Path(destination_root)
    target_root.mkdir(parents=True, exist_ok=True)
    for source_file in staging_root.iterdir():
        if source_file.is_file():
            shutil.copyfile(source_file, target_root / source_file.name)


# Some Excel/CSV writers use filesystem operations that are not supported directly
# against Unity Catalog Volume FUSE paths on shared compute. Generate complete files
# in local driver storage, then copy the completed files into the Volume.
staging_dir = None
conversion_output_root = output_root
if output_root.startswith("/Volumes/"):
    staging_dir = Path(tempfile.mkdtemp(prefix="audithero-convert-"))
    conversion_output_root = str(staging_dir / "canonical")

try:
    result = convert_source_files(
        source_root=source_root,
        mapping=mapping,
        output_root=conversion_output_root,
        write_workbook=True,
        strict=False,
    )

    if staging_dir is not None:
        _publish_staged_files(Path(conversion_output_root), output_root)
        result["output_root"] = output_root
        result["workbook"] = f"{output_root}/audithero_input.xlsx" if result.get("workbook") else None
finally:
    if staging_dir is not None:
        shutil.rmtree(staging_dir, ignore_errors=True)

display(result["report"])
print(f"Canonical workbook: {result['workbook']}")
if result["errors"]:
    print("Conversion completed with issues:")
    for issue in result["errors"]:
        print(" -", issue)
    if strict:
        raise ValueError("Source conversion failed:\n - " + "\n - ".join(result["errors"]))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Run File Readiness
# MAGIC
# MAGIC File Readiness checks whether the converted canonical data contains the required fields and evidence for an audit. Blocking findings must be resolved before payroll calculation.
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
