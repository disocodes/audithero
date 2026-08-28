from __future__ import annotations
from pathlib import Path
import pandas as pd
from .file_source import load_file_source, input_inventory

REQUIRED_COLUMNS = {
    "employees": {"employee_id","employee_name"},
    "pay_details": {"employee_id","effective_from","classification_code"},
    "employment_history": {"employee_id","start_date","employment_type"},
    "timesheets": {"timesheet_id","employee_id","start_datetime","end_datetime"},
}
OPTIONAL_COLUMNS = {
    "employees": {"state","work_group","employment_type_current"},
    "timesheets": {"pay_period_start","pay_period_end","location_state","holiday_location_key","unpaid_break_minutes"},
}


def assess_file_readiness(input_root, config_root):
    findings=[]
    def add(kind,key,status,detail): findings.append({"finding_type":kind,"source_key":key,"status":status,"detail":detail})
    inv=input_inventory(input_root)
    for _,r in inv.iterrows():
        if bool(r["required"]) and not bool(r["found"]): add("INPUT_DATASET",r["dataset"],"BLOCKING",f"Required dataset missing from {input_root}")
        elif bool(r["found"]): add("INPUT_DATASET",r["dataset"],"READY",str(r["file"]))
        else: add("INPUT_DATASET",r["dataset"],"OPTIONAL",f"Optional dataset not supplied: {r['dataset']}")
    try: frames=load_file_source(input_root)
    except Exception as exc:
        add("INPUT_LOAD","manual_files","BLOCKING",str(exc)); return pd.DataFrame(findings)

    for name,required in REQUIRED_COLUMNS.items():
        missing=sorted(required-set(frames[name].columns))
        if missing: add("INPUT_COLUMNS",name,"BLOCKING","Missing columns: "+", ".join(missing))
        else: add("INPUT_COLUMNS",name,"READY","Required columns present")
    for name,cols in OPTIONAL_COLUMNS.items():
        missing=sorted(cols-set(frames[name].columns))
        if missing: add("INPUT_COLUMNS_RECOMMENDED",name,"REVIEW","Recommended columns absent: "+", ".join(missing))

    pdets=frames["pay_details"]
    if "classification_code" in pdets.columns:
        blank=int(pdets["classification_code"].isna().sum()+(pdets["classification_code"].astype(str).str.strip()=="").sum())
        if blank: add("CLASSIFICATION","classification_code","BLOCKING",f"{blank} pay-detail row(s) lack a canonical SCHADS classification code")
    ts=frames["timesheets"]
    if "pay_period_start" not in ts.columns or ts["pay_period_start"].isna().any():
        add("PAY_PERIOD","pay_period_start","REVIEW","Some/all pay-period starts are absent; first-full-pay-period Award version selection may require review")

    root=Path(config_root)
    instruments=root/"industrial_instrument_history.csv"
    if not instruments.exists() or instruments.stat().st_size<20:
        add("CONTROL_REGISTER","industrial_instrument_history.csv","BLOCKING","Historical remediation requires evidence of Award/EA/IFA coverage")
    else: add("CONTROL_REGISTER","industrial_instrument_history.csv","READY","Instrument history register present")

    employment=frames["employment_history"]
    has_pt="employment_type" in employment.columns and employment["employment_type"].astype(str).str.upper().str.contains("PART").any()
    pt=root/"part_time_patterns.csv"
    if has_pt and (not pt.exists() or pt.stat().st_size<20):
        add("CONTROL_REGISTER","part_time_patterns.csv","BLOCKING","Part-time employees detected; effective-dated written pattern history is required")
    elif has_pt: add("CONTROL_REGISTER","part_time_patterns.csv","READY","Part-time pattern register present")

    payroll=frames["payroll_earnings"]
    if payroll.empty:
        add("ACTUAL_PAY","payroll_earnings","REVIEW","Entitlements can be calculated, but under/over-payment status requires actual payroll earnings")
    else:
        needed={"employee_id","pay_period_start","pay_period_end","pay_category","amount"}; miss=sorted(needed-set(payroll.columns))
        add("ACTUAL_PAY","payroll_earnings","BLOCKING" if miss else "READY",("Missing: "+", ".join(miss)) if miss else "Actual payroll earnings available")
    return pd.DataFrame(findings)
