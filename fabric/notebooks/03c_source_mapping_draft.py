# AuditHero Fabric notebook source
#
# PURPOSE
# -------
# Build an editable Excel mapping workbook from CSV/XLSX payroll, HR, roster and
# timekeeping exports. The notebook inspects file names, Excel sheet names and
# column headings and proposes matches to AuditHero's canonical input model. It
# does not calculate payroll.

from pathlib import Path
import pandas as pd

try:
    from schads_audit.source_mapping import scan_source_items, generate_mapping_draft
    from schads_audit.mapping_workbook import write_mapping_workbook
except ModuleNotFoundError as exc:
    if exc.name == "schads_audit" or str(exc.name or "").startswith("schads_audit."):
        raise RuntimeError(
            "AuditHero is not available in the current Fabric Spark session. "
            "Confirm that AuditHero_Environment is attached to this notebook, then "
            "start a new Spark session and run the notebook again."
        ) from exc
    raise


def _normalize_fabric_lakehouse_path(value: str) -> str:
    """Normalize Fabric Lakehouse paths to the default notebook mount."""
    text = str(value or "").strip()
    for source, target in (
        ("/lakehouse/Files", "/lakehouse/default/Files"),
        ("/lakehouse/Tables", "/lakehouse/default/Tables"),
    ):
        if text == source or text.startswith(source + "/"):
            normalized = target + text[len(source):]
            print(f"Normalized Fabric Lakehouse path: {text} -> {normalized}")
            return normalized
    return text


# Parameters supplied by the Fabric pipeline. They can also be set when the
# notebook is run directly.
# source_root: folder containing the original exports.
# draft_path: location for the editable mapping workbook.
# overwrite: whether an existing draft can be replaced.
source_root = _normalize_fabric_lakehouse_path(source_root)
draft_path = _normalize_fabric_lakehouse_path(draft_path)

print("STEP 1 — Inspect raw source files")
source_dir = Path(source_root)
if not source_dir.exists():
    source_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created AuditHero raw-import folder: {source_root}")

inventory = scan_source_items(source_root)
if inventory.empty:
    raise ValueError(
        f"No CSV/XLSX files were found under {source_root}. "
        "Upload the payroll, HR, roster or timekeeping exports to this Lakehouse Files folder "
        "and run this notebook again."
    )
display(inventory[["file", "sheet", "item_name", "sample_rows", "columns"]])

print("STEP 2 — Suggest canonical dataset and field matches")
draft_file = Path(draft_path)
draft_file.parent.mkdir(parents=True, exist_ok=True)
if draft_file.exists() and str(overwrite).lower() not in {"true", "1", "yes"}:
    raise FileExistsError(
        f"{draft_path} already exists. Set overwrite=true only when the existing draft should be replaced."
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

print("STEP 3 — Review and approve the mapping")
print(f"Mapping draft created: {draft_path}")
print("Download the workbook from the Lakehouse Files area, review field_mapping, add value translations if required, and upload the approved workbook as source_mapping.xlsx.")
print("NEXT: run 'AuditHero - Convert Mapped Files and Run Audit'.")
print("Use 'AuditHero - Convert Source Files' when conversion and File Readiness need to be checked without running the payroll audit.")

notebookutils.notebook.exit(draft_path)
