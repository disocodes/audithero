# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Build a Source Mapping Workbook
# MAGIC
# MAGIC **Purpose:** create an editable source-mapping workbook when payroll, HR, roster or timekeeping exports do not already use AuditHero's canonical field names.
# MAGIC
# MAGIC The notebook scans CSV and Excel files in the raw import folder, compares file/sheet names and column headings with AuditHero's canonical fields, and creates `source_mapping_draft.xlsx`. No payroll calculations are performed.
# MAGIC
# MAGIC **Workflow:** upload raw exports → run this notebook → review and save `source_mapping.xlsx` → run **AuditHero - Convert Mapped Files and Run Audit**.
# COMMAND ----------
# MAGIC %pip install "openpyxl>=3.1"
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Read Job parameters
# MAGIC
# MAGIC The parameters are exposed by the Databricks Job and can also be set when this notebook is run directly. Blank path values use the standard AuditHero Unity Catalog Volume locations.
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

from schads_audit.source_mapping import scan_source_items, generate_mapping_draft
from schads_audit.mapping_workbook import write_mapping_workbook

# Job parameters. `catalog` determines the default Volume paths.
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("source_root", "")
dbutils.widgets.text("draft_path", "")
dbutils.widgets.dropdown("overwrite", "false", ["false", "true"])

catalog = dbutils.widgets.get("catalog")
source_root = dbutils.widgets.get("source_root").strip() or f"/Volumes/{catalog}/bronze/landing/import/raw"
draft_path = dbutils.widgets.get("draft_path").strip() or f"/Volumes/{catalog}/bronze/landing/import/source_mapping_draft.xlsx"
overwrite = dbutils.widgets.get("overwrite").lower() == "true"

print(f"Raw source folder: {source_root}")
print(f"Mapping draft:     {draft_path}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Inspect uploaded files and sheets
# MAGIC
# MAGIC `scan_source_items` reads a small sample of each CSV file or Excel sheet to identify the source structure and column headings.
# COMMAND ----------
inventory = scan_source_items(source_root)
if inventory.empty:
    raise ValueError(
        f"No CSV/XLSX files were found under {source_root}. Upload the source exports in Catalog Explorer, then run this job again."
    )
display(inventory[["file", "sheet", "item_name", "sample_rows", "columns"]])
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Generate mapping suggestions
# MAGIC
# MAGIC AuditHero compares source headings with the canonical schema and proposes dataset and field matches. Review every required field before conversion, especially classifications, employment type, dates and payroll amounts.
# COMMAND ----------
def _volume_uri(path: str) -> str:
    return f"dbfs:{path}" if path.startswith("/Volumes/") else path


def _path_exists(path: str) -> bool:
    if path.startswith("/Volumes/"):
        try:
            dbutils.fs.ls(_volume_uri(path))
            return True
        except Exception:
            return False
    return Path(path).exists()


def _write_mapping_draft(mapping: dict, destination: str) -> None:
    """Create the Excel workbook locally, then publish it to the configured destination."""
    if not destination.startswith("/Volumes/"):
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        write_mapping_workbook(mapping, target)
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="audithero-mapping-"))
    local_file = temp_dir / Path(destination).name
    try:
        write_mapping_workbook(mapping, local_file)
        destination_parent = destination.rsplit("/", 1)[0]
        dbutils.fs.mkdirs(_volume_uri(destination_parent))
        copied = dbutils.fs.cp(local_file.as_uri(), _volume_uri(destination), True)
        if copied is False:
            raise OSError(f"Databricks could not copy the mapping workbook to {destination}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if _path_exists(draft_path) and not overwrite:
    raise FileExistsError(
        f"{draft_path} already exists. Set overwrite=true if the existing draft should be replaced."
    )

draft = generate_mapping_draft(source_root)
_write_mapping_draft(draft, draft_path)

summary_rows = []
for dataset, cfg in draft["datasets"].items():
    source = cfg.get("source") or {}
    summary_rows.append({
        "dataset": dataset,
        "suggested": bool(cfg.get("enabled")),
        "source_file": source.get("file"),
        "source_sheet": source.get("sheet"),
        "confidence": cfg.get("_dataset_confidence"),
        "mapped_fields": len(cfg.get("columns") or {}),
    })

import pandas as pd
summary = pd.DataFrame(summary_rows)
display(summary.sort_values(["suggested", "confidence"], ascending=[False, False]))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Review and approve the mapping
# MAGIC
# MAGIC In **Catalog Explorer**, download `source_mapping_draft.xlsx`, review the `field_mapping` sheet, add source-value translations on `value_mapping` where required, and upload the approved workbook as `source_mapping.xlsx`.
# MAGIC
# MAGIC The conversion workflow stops when required AuditHero fields are not mapped. Mapping workbooks cannot execute arbitrary Python or formulas.
# COMMAND ----------
print("Mapping draft created successfully.")
print(draft_path)
print("NEXT: review the workbook, upload it as source_mapping.xlsx, then run 'AuditHero - Convert Mapped Files and Run Audit'.")
print("Use 'AuditHero - Convert Source Files' when conversion and File Readiness need to be checked without running the payroll audit.")
