# AuditHero Fabric notebook source
#
# PURPOSE
# -------
# Convert payroll, HR, roster and timekeeping CSV/XLSX exports into AuditHero's
# canonical input files using an approved source_mapping.xlsx or JSON mapping.
# When payroll earnings are supplied, the approved workbook must also contain
# pay-category treatments used for actual-pay reconciliation. The notebook runs
# File Readiness after conversion. It does not calculate payroll.

from pathlib import Path
import pandas as pd

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


def _load_pay_category_treatments(path: Path) -> pd.DataFrame | None:
    """Load and validate operator-approved payroll category treatments."""
    if path.suffix.lower() not in {".xlsx", ".xlsm"}:
        return None
    try:
        table = pd.read_excel(path, sheet_name="pay_category_treatment")
    except ValueError:
        return None

    required = {"pay_category", "treatment"}
    if not required.issubset(table.columns):
        raise ValueError(
            "The pay_category_treatment sheet must contain pay_category and treatment columns. "
            "Regenerate the mapping workbook and review it before conversion."
        )

    table = table.copy()
    table["pay_category"] = table["pay_category"].fillna("").astype(str).str.strip()
    table["treatment"] = table["treatment"].fillna("").astype(str).str.strip().str.upper()
    table = table[table["pay_category"] != ""].copy()

    allowed = {"AUDITABLE_WORK", "ALLOWANCE", "EXCLUDE"}
    invalid = table[(table["treatment"] != "") & (~table["treatment"].isin(allowed))]
    if not invalid.empty:
        bad = ", ".join(sorted(invalid["pay_category"].unique().tolist()))
        raise ValueError(
            "Invalid pay-category treatment value(s) for: " + bad + ". "
            "Use only AUDITABLE_WORK, ALLOWANCE or EXCLUDE."
        )

    incomplete = table[table["treatment"] == ""]
    if not incomplete.empty:
        missing = ", ".join(sorted(incomplete["pay_category"].unique().tolist()))
        raise ValueError(
            "Complete the pay_category_treatment sheet before conversion. "
            f"Treatment is missing for: {missing}. "
            "Review each category and select AUDITABLE_WORK, ALLOWANCE or EXCLUDE."
        )
    return table


def _write_pay_category_mapping(result: dict, destination_root: Path, treatments: pd.DataFrame | None) -> None:
    """Create the canonical pay-category mapping used by readiness and reconciliation."""
    payroll = result.get("frames", {}).get("payroll_earnings")
    if payroll is None or payroll.empty:
        return

    if treatments is None:
        raise ValueError(
            "Payroll earnings are supplied but source_mapping.xlsx has no pay_category_treatment sheet. "
            "Run 'AuditHero - Build Source Mapping Workbook' again, review the pay-category treatments, "
            "and upload the approved workbook as source_mapping.xlsx."
        )

    actual_categories = (
        set(payroll["pay_category"].dropna().astype(str).str.strip())
        if "pay_category" in payroll.columns
        else set()
    )
    approved_categories = set(treatments["pay_category"])
    missing = sorted(category for category in actual_categories if category and category not in approved_categories)
    if missing:
        raise ValueError(
            "The approved mapping workbook does not cover all pay categories present in payroll earnings. "
            "Add treatment rows for: " + ", ".join(missing)
        )

    mapping_frame = treatments[["pay_category", "treatment"]].copy()
    mapping_frame["source_key"] = mapping_frame["pay_category"]
    mapping_frame["source_label"] = mapping_frame["pay_category"]
    mapping_frame = mapping_frame[["source_key", "source_label", "treatment"]].drop_duplicates()
    mapping_frame.to_csv(destination_root / "pay_category_mapping.csv", index=False)
    result["frames"]["pay_category_mapping"] = mapping_frame
    print(f"Approved pay-category treatments: {len(mapping_frame)}")


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
# Pay-category treatment is controlled through the dedicated workbook sheet.
if "pay_category_mapping" in (mapping.get("datasets") or {}):
    mapping["datasets"]["pay_category_mapping"]["enabled"] = False
    mapping["datasets"]["pay_category_mapping"]["source"] = None
    mapping["datasets"]["pay_category_mapping"]["columns"] = {}

enabled = [name for name, cfg in mapping.get("datasets", {}).items() if cfg.get("enabled")]
print("Datasets enabled for conversion:", ", ".join(enabled) or "NONE")
pay_category_treatments = _load_pay_category_treatments(mapping_file)

source_dir = Path(source_root)
if not source_dir.exists():
    raise FileNotFoundError(
        f"Source folder not found: {source_root}. Upload the raw exports to the AuditHero Lakehouse Files import/raw folder first."
    )
output_dir = Path(output_root)
output_dir.mkdir(parents=True, exist_ok=True)

print("STEP 2 — Convert source fields to AuditHero canonical fields")
result = convert_source_files(
    source_root=source_root,
    mapping=mapping,
    output_root=output_root,
    write_workbook=True,
    strict=False,
)
_write_pay_category_mapping(result, output_dir, pay_category_treatments)

display(result["report"])
print(f"Canonical workbook written to: {result['workbook']}")
if result["errors"]:
    print("Conversion completed with issues:")
    for issue in result["errors"]:
        print(" -", issue)
    if str(strict).lower() in {"true", "1", "yes"}:
        raise ValueError("Source conversion failed:\n - " + "\n - ".join(result["errors"]))

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
