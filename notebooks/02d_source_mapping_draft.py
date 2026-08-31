# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Build a Source Mapping Workbook
# MAGIC
# MAGIC Use this notebook when your payroll, HR, roster or timekeeping exports do **not** already use AuditHero's standard column names.
# MAGIC
# MAGIC The notebook scans CSV and Excel files in the raw import folder, compares file/sheet names and column headers with AuditHero's canonical fields, and creates an editable `source_mapping_draft.xlsx` workbook. No payroll calculations are performed here.
# MAGIC
# MAGIC **Typical workflow:** upload raw exports → run this notebook → download/edit the mapping workbook → upload it back as `source_mapping.xlsx` → run **AuditHero - Convert Source Files**.
# COMMAND ----------
# MAGIC %pip install "openpyxl>=3.1"
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Read job parameters
# MAGIC
# MAGIC These widgets are also exposed as Databricks Job parameters. If you run the notebook directly, you can change them at the top of the notebook. Leaving a path blank uses the standard AuditHero Unity Catalog Volume locations.
# COMMAND ----------
from pathlib import Path
import sys

ROOT = Path.cwd()
for candidate in (ROOT, *ROOT.parents):
    if (candidate / "src" / "schads_audit").exists():
        sys.path.insert(0, str(candidate / "src"))
        break

from schads_audit.source_mapping import scan_source_items, generate_mapping_draft
from schads_audit.mapping_workbook import write_mapping_workbook

# Job/UI parameters. The catalog value is used only to build friendly defaults.
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
# MAGIC `scan_source_items` reads only enough rows to identify each CSV file or Excel sheet and its headers. The inventory lets you confirm that AuditHero can see the exports you uploaded before it tries to suggest mappings.
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
# MAGIC AuditHero compares common payroll terms such as `Employee Number`, `Clock In`, `Pay Category` and `Employment Type` with the canonical schema. Suggestions are deliberately treated as a **draft**. Review every required field before conversion, especially classifications, employment type, dates and amounts.
# COMMAND ----------
draft_file = Path(draft_path)
if draft_file.exists() and not overwrite:
    raise FileExistsError(
        f"{draft_path} already exists. Set overwrite=true if you intentionally want to replace the existing draft."
    )

draft = generate_mapping_draft(source_root)
write_mapping_workbook(draft, draft_file)

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
# MAGIC ## 4. What to do next
# MAGIC
# MAGIC In **Catalog Explorer**, open the Volume path printed below and download `source_mapping_draft.xlsx`. Review the `field_mapping` sheet, correct the proposed matches, optionally add source-value translations on `value_mapping`, then upload the edited file as `source_mapping.xlsx`.
# MAGIC
# MAGIC The conversion job will stop if a required AuditHero field is not mapped. It does not execute formulas or arbitrary code from the mapping workbook.
# COMMAND ----------
print("Mapping draft created successfully.")
print(draft_path)
print("NEXT: edit the workbook, upload it as source_mapping.xlsx, then run 'AuditHero - Convert Source Files'.")
