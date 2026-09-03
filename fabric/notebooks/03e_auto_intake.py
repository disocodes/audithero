# AuditHero — Auto Prepare Uploaded Files
#
# PURPOSE
# -------
# Identify ordinary timesheet and employee/pay-rate CSV/XLSX files and prepare
# canonical AuditHero inputs without requiring a mapping workbook.
#
# A usable timesheet needs an employee name or identifier plus shift start and end.
# Optional files or columns enrich hours, employee rates, rate effective dates,
# employment type, classification, state, work type and pay-period dates.

from pathlib import Path
import json
import shutil

from schads_audit.auto_intake import build_auto_canonical

source_root = str(globals().get("source_root", "/lakehouse/default/Files/import/raw") or "/lakehouse/default/Files/import/raw")
output_root = str(globals().get("output_root", "/lakehouse/default/Files/auto_input") or "/lakehouse/default/Files/auto_input")
start_override = str(globals().get("start_date", "") or "").strip()
end_override = str(globals().get("end_date", "") or "").strip()

print(f"Source folder: {source_root}")
print(f"Automatic canonical folder: {output_root}")

print("STEP 1 — Detect source files and fields")
result = build_auto_canonical(source_root)
frames = result["frames"]
metadata = result["metadata"]
start_date = start_override or str(metadata.get("start_date") or "")
end_date = end_override or str(metadata.get("end_date") or "")
if not start_date or not end_date:
    raise ValueError("AuditHero could not determine the audit date range from the supplied shifts.")

print("STEP 2 — Publish automatic canonical inputs")
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

manifest = {
    **metadata,
    "audit_start_date": start_date,
    "audit_end_date": end_date,
    "mode": "AUTO_INTAKE",
}
(out / "auto_intake_manifest.json").write_text(
    json.dumps(manifest, indent=2, default=str), encoding="utf-8"
)

print("STEP 3 — Automatic preparation summary")
print(f"Employees identified: {metadata.get('employees', 0)}")
print(f"Timesheet rows identified: {metadata.get('timesheets', 0)}")
print(f"Effective-dated rate rows identified: {metadata.get('rate_history_rows', 0)}")
print(f"Audit window: {start_date} to {end_date}")
for warning in metadata.get("warnings", []) or []:
    print(f"REVIEW: {warning}")

payload = {
    "status": "SUCCESS",
    "output_root": output_root,
    "start_date": start_date,
    "end_date": end_date,
    "employees": metadata.get("employees", 0),
    "timesheets": metadata.get("timesheets", 0),
}
notebookutils.notebook.exit("AUDITHERO_SUCCESS:" + json.dumps(payload))
