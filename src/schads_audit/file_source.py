from __future__ import annotations
from pathlib import Path
import pandas as pd

CORE_INPUTS = {
    "employees":"employees",
    "pay_details":"pay_details",
    "employment_history":"employment_history",
    "timesheets":"timesheets",
    "rostered_shifts":"rostered_shifts",
    "payroll_earnings":"payroll_earnings",
    "pay_runs":"pay_runs",
}
CONTROL_INPUTS = {
    "industrial_instrument_history":"industrial_instrument_history",
    "part_time_patterns":"part_time_patterns",
    "part_time_variations":"part_time_variations",
    "public_holiday_overrides":"public_holiday_overrides",
    "overtime_rest_controls":"overtime_rest_controls",
    "meal_break_events":"meal_break_events",
    "supplemental_events":"supplemental_events",
    "toil_register":"toil_register",
    "pay_category_mapping":"pay_category_mapping",
}
CANONICAL_INPUTS={**CORE_INPUTS,**CONTROL_INPUTS}
WORKBOOK_NAMES=("audithero_input.xlsx","audithero_input.xlsm")


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower()==".csv": return pd.read_csv(path)
    if path.suffix.lower() in {".xlsx",".xlsm"}: return pd.read_excel(path)
    raise ValueError(f"Unsupported input format: {path.name}")


def _resolve(root: Path,stem: str):
    for ext in (".csv",".xlsx",".xlsm"):
        p=root/f"{stem}{ext}"
        if p.exists(): return p
    return None


def _load_workbook(root: Path):
    workbook=next((root/n for n in WORKBOOK_NAMES if (root/n).exists()),None)
    if not workbook: return None,{}
    book=pd.ExcelFile(workbook); lookup={s.lower():s for s in book.sheet_names}; frames={}
    for key,stem in CANONICAL_INPUTS.items():
        sheet=lookup.get(stem.lower())
        frames[key]=pd.read_excel(workbook,sheet_name=sheet) if sheet else pd.DataFrame()
    return workbook,frames


def load_file_source(input_root: str|Path,start_date=None,end_date=None)->dict[str,pd.DataFrame]:
    """Load a self-contained AuditHero workbook or separate CSV/XLSX files.

    Required core datasets are employees, pay_details, employment_history and
    timesheets. Optional sheets/files may provide rosters, actual payroll and the
    compliance control registers. Sidecar config files remain supported; the
    manual audit flow prefers workbook/file control sheets when supplied.
    """
    root=Path(input_root)
    if not root.exists(): raise FileNotFoundError(f"AuditHero input folder does not exist: {root}")
    workbook,frames=_load_workbook(root)
    if not workbook:
        frames={}
        for key,stem in CANONICAL_INPUTS.items():
            p=_resolve(root,stem); frames[key]=_read_table(p) if p else pd.DataFrame()
    required=["employees","pay_details","employment_history","timesheets"]
    missing=[k for k in required if frames[k].empty]
    if missing:
        source=f"workbook {workbook.name}" if workbook else str(root)
        raise ValueError("Missing required manual input dataset(s): "+", ".join(missing)+f". Source checked: {source}.")
    if start_date or end_date:
        ts=frames["timesheets"].copy()
        if "start_datetime" not in ts.columns: raise ValueError("timesheets input must contain start_datetime")
        d=pd.to_datetime(ts["start_datetime"],errors="coerce")
        if start_date:
            ts=ts[d>=pd.to_datetime(start_date)]; d=pd.to_datetime(ts["start_datetime"],errors="coerce")
        if end_date: ts=ts[d<pd.to_datetime(end_date)+pd.Timedelta(days=1)]
        frames["timesheets"]=ts
    return frames


def input_inventory(input_root: str|Path)->pd.DataFrame:
    root=Path(input_root); workbook,workbook_frames=_load_workbook(root) if root.exists() else (None,{})
    rows=[]
    for key,stem in CANONICAL_INPUTS.items():
        if workbook:
            found=not workbook_frames.get(key,pd.DataFrame()).empty; file=f"{workbook}#{stem}" if found else None
        else:
            p=_resolve(root,stem) if root.exists() else None; found=bool(p); file=str(p) if p else None
        rows.append({"dataset":key,"required":key in {"employees","pay_details","employment_history","timesheets"},"category":"CORE" if key in CORE_INPUTS else "CONTROL","found":found,"file":file})
    return pd.DataFrame(rows)
