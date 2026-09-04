# AuditHero — Preview and Prepare Uploaded Files
#
# PURPOSE
# -------
# Inspect ordinary payroll, timesheet and employee/rate CSV/XLSX files, show
# AuditHero's interpretation, and prepare canonical inputs without starting an audit.
# Review the preview before running the prepared-file audit. Use Advanced Mapping
# only when a file role or field needs correction or additional context.

from pathlib import Path
import json
import shutil
import pandas as pd

from schads_audit.auto_intake import build_auto_canonical

source_root = str(globals().get("source_root", "/lakehouse/default/Files/import/raw") or "/lakehouse/default/Files/import/raw")
output_root = str(globals().get("output_root", "/lakehouse/default/Files/auto_input") or "/lakehouse/default/Files/auto_input")
start_override = str(globals().get("start_date", "") or "").strip()
end_override = str(globals().get("end_date", "") or "").strip()

print(f"Source folder: {source_root}")
print(f"Prepared canonical folder: {output_root}")

print("STEP 1 — Detect source files and fields")
result = build_auto_canonical(source_root)
frames = result["frames"]
metadata = result["metadata"]
start_date = start_override or str(metadata.get("start_date") or "")
end_date = end_override or str(metadata.get("end_date") or "")
if not start_date or not end_date:
    raise ValueError("AuditHero could not determine the audit date range from the supplied shifts.")

interpretation = pd.DataFrame(metadata.get("interpretation") or [])
if not interpretation.empty:
    display(interpretation)
for warning in metadata.get("warnings", []) or []:
    print(f"REVIEW: {warning}")

print("STEP 2 — Publish prepared canonical inputs and interpretation evidence")
out = Path(output_root)
if out.exists():
    for child in out.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
out.mkdir(parents=True, exist_ok=True)

for name, frame in frames.items():
    if frame is None or frame.empty:
        continue
    frame.to_csv(out / f"{name}.csv", index=False)
    print(f"  {name}: {len(frame):,} row(s)")

if not interpretation.empty:
    export_preview = interpretation.copy()
    export_preview["detected_roles"] = export_preview["detected_roles"].map(lambda x: json.dumps(x, default=str))
    export_preview["mapped_fields"] = export_preview["mapped_fields"].map(lambda x: json.dumps(x, default=str))
    export_preview.to_csv(out / "auto_intake_preview.csv", index=False)

manifest = {
    **metadata,
    "audit_start_date": start_date,
    "audit_end_date": end_date,
    "mode": "AUTO_INTAKE_PREVIEW",
}
(out / "auto_intake_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

print("STEP 3 — Preparation summary")
print(f"Employees identified: {metadata.get('employees', 0)}")
print(f"Timesheet rows identified: {metadata.get('timesheets', 0)}")
print(f"Payroll earning rows identified: {metadata.get('payroll_earning_rows', 0)}")
print(f"Effective-dated rate rows identified: {metadata.get('rate_history_rows', 0)}")
print(f"Audit window: {start_date} to {end_date}")
print("Preview preparation complete. Review the interpretation before starting the prepared-file audit.")
print("If a role or field is wrong, use the Advanced Mapping workbook and the mapped-file workflow instead.")

payload = {
    "status": "SUCCESS",
    "output_root": output_root,
    "start_date": start_date,
    "end_date": end_date,
    "employees": metadata.get("employees", 0),
    "timesheets": metadata.get("timesheets", 0),
    "payroll_earning_rows": metadata.get("payroll_earning_rows", 0),
}
notebookutils.notebook.exit("AUDITHERO_SUCCESS:" + json.dumps(payload))
