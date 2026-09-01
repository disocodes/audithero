# AuditHero Fabric notebook source
#
# PURPOSE
# -------
# Convert payroll, HR, roster and timekeeping CSV/XLSX exports into AuditHero's
# canonical input files using an approved source_mapping.xlsx or JSON mapping.
# The notebook also runs File Readiness. It does not calculate payroll.

from pathlib import Path

try:
    from schads_audit.mapping_workbook import load_mapping
    from schads_audit.source_mapping import convert_source_files
    from schads_audit.file_readiness import assess_file_readiness
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


source_root = _normalize_fabric_lakehouse_path(source_root)
mapping_path = _normalize_fabric_lakehouse_path(mapping_path)
output_root = _normalize_fabric_lakehouse_path(output_root)

print("STEP 1 — Load the approved source mapping")
mapping_file = Path(mapping_path)
if not mapping_file.exists():
    raise FileNotFoundError(
        f"Mapping file not found: {mapping_path}. Run 'AuditHero - Build Source Mapping Workbook', review the draft, and upload it as source_mapping.xlsx."
    )
mapping = load_mapping(mapping_file)
enabled = [name for name, cfg in mapping.get("datasets", {}).items() if cfg.get("enabled")]
print("Datasets enabled for conversion:", ", ".join(enabled) or "NONE")

source_dir = Path(source_root)
if not source_dir.exists():
    raise FileNotFoundError(
        f"Source folder not found: {source_root}. Upload the raw exports to the AuditHero Lakehouse Files import/raw folder first."
    )
Path(output_root).mkdir(parents=True, exist_ok=True)

print("STEP 2 — Convert source fields to AuditHero canonical fields")
result = convert_source_files(
    source_root=source_root,
    mapping=mapping,
    output_root=output_root,
    write_workbook=True,
    strict=str(strict).lower() in {"true", "1", "yes"},
)
display(result["report"])
print(f"Canonical workbook written to: {result['workbook']}")

print("STEP 3 — Validate the converted canonical files")
# Readiness uses the canonical output folder for data and optional sidecar control files.
readiness = assess_file_readiness(output_root, output_root)
display(readiness)
blocking = readiness[readiness["status"] == "BLOCKING"] if not readiness.empty else readiness
if len(blocking):
    display(blocking)
    raise ValueError(
        f"Conversion completed, but {len(blocking)} blocking File Readiness item(s) remain. Correct the source mapping or source data and rerun conversion."
    )

print("Source conversion and File Readiness completed successfully.")
print("NEXT: run 'AuditHero - Uploaded Files Audit Pipeline' and choose the audit date range.")
notebookutils.notebook.exit(result["workbook"] or output_root)
