from __future__ import annotations
from pathlib import Path
import pandas as pd
from .file_source import load_file_source, input_inventory
from .canonical_normalization import normalize_canonical_frames

REQUIRED_COLUMNS={
 "employees":{"employee_id","employee_name"},
 "pay_details":{"employee_id","effective_from","classification_code"},
 "employment_history":{"employee_id","start_date","employment_type"},
 "timesheets":{"timesheet_id","employee_id","start_datetime","end_datetime"},
}
OPTIONAL_COLUMNS={
 "employees":{"state","work_group","employment_type_current"},
 "timesheets":{"pay_period_start","pay_period_end","location_state","holiday_location_key","unpaid_break_minutes"},
}


def _sidecar_present(root: Path,name: str):
    p=root/f"{name}.csv"; return p.exists() and p.stat().st_size>20


def _control_present(frames,root,name):
    df=frames.get(name); return (df is not None and not df.empty) or _sidecar_present(root,name)


def assess_file_readiness(input_root,config_root):
    findings=[]
    def add(kind,key,status,detail): findings.append({"finding_type":kind,"source_key":key,"status":status,"detail":detail})
    inv=input_inventory(input_root)
    for _,r in inv.iterrows():
        if bool(r["required"]) and not bool(r["found"]): add("INPUT_DATASET",r["dataset"],"BLOCKING",f"Required dataset missing from {input_root}")
        elif bool(r["found"]): add("INPUT_DATASET",r["dataset"],"READY",str(r["file"]))
        elif r.get("category")=="CORE": add("INPUT_DATASET",r["dataset"],"OPTIONAL",f"Optional core dataset not supplied: {r['dataset']}")
    try: frames=normalize_canonical_frames(load_file_source(input_root))
    except Exception as exc:
        add("INPUT_LOAD","manual_files","BLOCKING",str(exc)); return pd.DataFrame(findings)

    for name,required in REQUIRED_COLUMNS.items():
        missing=sorted(required-set(frames[name].columns)); add("INPUT_COLUMNS",name,"BLOCKING" if missing else "READY",("Missing columns: "+", ".join(missing)) if missing else "Required columns present")
    for name,cols in OPTIONAL_COLUMNS.items():
        missing=sorted(cols-set(frames[name].columns))
        if missing: add("INPUT_COLUMNS_RECOMMENDED",name,"REVIEW","Recommended columns absent: "+", ".join(missing))

    for dataset,frame in frames.items():
        if frame is None or frame.empty:
            continue
        for column in frame.columns:
            if not str(column).startswith("_invalid_"):
                continue
            count=int(frame[column].fillna(False).astype(bool).sum())
            if count:
                field=str(column)[len("_invalid_"):]
                add("INPUT_VALUE_TYPE",f"{dataset}.{field}","REVIEW",f"{count} non-blank value(s) could not be converted to the canonical numeric type; affected calculations will be marked for review")

    pdets=frames["pay_details"]
    if "classification_code" in pdets.columns:
        blank=pdets["classification_code"].isna()|(pdets["classification_code"].fillna("").astype(str).str.strip()=="")
        if int(blank.sum()): add("CLASSIFICATION","classification_code","BLOCKING",f"{int(blank.sum())} pay-detail row(s) lack a canonical SCHADS classification code")

    ts=frames["timesheets"]; pay_runs=frames.get("pay_runs",pd.DataFrame())
    missing_period="pay_period_start" not in ts.columns or ts["pay_period_start"].isna().any()
    if missing_period and (pay_runs is None or pay_runs.empty): add("PAY_PERIOD","pay_period_start","REVIEW","Some/all timesheets lack pay-period start and no pay_runs sheet was supplied; first-full-pay-period Award version selection may require review")
    elif missing_period: add("PAY_PERIOD","pay_runs","READY","pay_runs supplied; unique matching periods can be assigned automatically")

    root=Path(config_root)
    if not _control_present(frames,root,"industrial_instrument_history"):
        add("CONTROL_REGISTER","industrial_instrument_history","BLOCKING","Historical remediation requires Award/EA/IFA coverage evidence; add the workbook sheet or sidecar CSV")
    else: add("CONTROL_REGISTER","industrial_instrument_history","READY","Instrument history evidence present")

    employment=frames["employment_history"]; has_pt="employment_type" in employment.columns and employment["employment_type"].astype(str).str.upper().str.contains("PART").any()
    if has_pt and not _control_present(frames,root,"part_time_patterns"):
        add("CONTROL_REGISTER","part_time_patterns","BLOCKING","Part-time employees detected; add effective-dated written pattern history")
    elif has_pt: add("CONTROL_REGISTER","part_time_patterns","READY","Part-time pattern evidence present")

    payroll=frames["payroll_earnings"]
    if payroll.empty:
        add("ACTUAL_PAY","payroll_earnings","REVIEW","Expected entitlements can be calculated; actual-pay reconciliation is unavailable because payroll earnings were not supplied")
    else:
        needed={"employee_id","pay_period_start","pay_period_end","pay_category","amount"}; miss=sorted(needed-set(payroll.columns))
        invalid_required=[field for field in needed if field in payroll.columns and payroll[field].isna().any()]
        if miss or invalid_required:
            details=[]
            if miss: details.append("Missing: "+", ".join(miss))
            if invalid_required: details.append("Blank/invalid values: "+", ".join(sorted(invalid_required)))
            add("ACTUAL_PAY","payroll_earnings","REVIEW","Payroll earnings were supplied but actual-pay reconciliation is unavailable. "+"; ".join(details))
        else:
            add("ACTUAL_PAY","payroll_earnings","READY","Actual payroll earnings available")
            mapping=frames.get("pay_category_mapping",pd.DataFrame())
            sidecar=(root/"pay_category_mapping.json").exists()
            if (mapping is None or mapping.empty) and not sidecar:
                add("ACTUAL_PAY","pay_category_mapping","REVIEW","Payroll earnings are available but no pay-category treatment mapping exists; expected entitlements can still be calculated")
            else: add("ACTUAL_PAY","pay_category_mapping","READY","Pay-category treatment mapping available")
    return pd.DataFrame(findings)
