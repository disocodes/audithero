# AuditHero Fabric notebook source
#
# PURPOSE
# -------
# Build an editable Excel mapping workbook from arbitrary CSV/XLSX payroll exports.
# This notebook does not calculate pay. It only inspects file names, Excel sheet
# names and headers so an operator can match their fields to AuditHero's standard
# input model before conversion.

from pathlib import Path
import pandas as pd

from schads_audit.source_mapping import scan_source_items, generate_mapping_draft
from schads_audit.mapping_workbook import write_mapping_workbook

# Parameters supplied by the Fabric pipeline. They are deliberately ordinary
# strings so an operator can also run this notebook directly from the Fabric UI.
# source_root: folder containing the original exports.
# draft_path: where the editable mapping workbook will be written.
# overwrite: whether an existing draft may be replaced.

print("STEP 1 — Inspect raw source files")
inventory = scan_source_items(source_root)
if inventory.empty:
    raise ValueError(
        f"No CSV/XLSX files were found under {source_root}. Upload exports to the Lakehouse Files area and run this notebook again."
    )
display(inventory[["file", "sheet", "item_name", "sample_rows", "columns"]])

print("STEP 2 — Suggest canonical dataset and field matches")
draft_file = Path(draft_path)
if draft_file.exists() and str(overwrite).lower() not in {"true", "1", "yes"}:
    raise FileExistsError(
        f"{draft_path} already exists. Set overwrite=true only if you intentionally want to replace the current draft."
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
        "suggested_fields": len(cfg.get("columns") or {}),
    })
summary = pd.DataFrame(summary_rows)
display(summary.sort_values(["suggested", "confidence"], ascending=[False, False]))

print("STEP 3 — Operator action")
print(f"Mapping draft created: {draft_path}")
print("Open/download the workbook from the Lakehouse Files area, review field_mapping, add value translations if required, and upload the approved file as source_mapping.xlsx.")
print("Then run the Fabric pipeline 'AuditHero - Convert Source Files'.")

notebookutils.notebook.exit(draft_path)
