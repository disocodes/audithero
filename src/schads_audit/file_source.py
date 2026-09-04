from __future__ import annotations
from pathlib import Path
import pandas as pd

from .canonical_normalization import parse_datetime_series, parse_datetime_value

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
    "rest_break_controls":"rest_break_controls",
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


def _range_bounds(start_date=None,end_date=None):
    lower=parse_datetime_value(start_date) if start_date not in (None,"") else pd.NaT
    upper=parse_datetime_value(end_date) if end_date not in (None,"") else pd.NaT
    if not pd.isna(lower): lower=lower.normalize()
    if not pd.isna(upper): upper=upper.normalize()+pd.Timedelta(days=1)
    if not pd.isna(lower) and not pd.isna(upper) and upper<=lower:
        raise ValueError(f"end_date must be on or after start_date: {start_date} to {end_date}")
    return lower,upper


def _filter_overlap(frame: pd.DataFrame,start_col: str,end_col: str|None,lower,upper)->pd.DataFrame:
    if frame is None or frame.empty or start_col not in frame.columns:return frame
    starts=parse_datetime_series(frame[start_col])
    if end_col and end_col in frame.columns:
        ends=parse_datetime_series(frame[end_col])
    else:
        ends=starts
    mask=pd.Series(True,index=frame.index)
    if not pd.isna(lower):mask&=(ends.isna()|(ends>=lower))
    if not pd.isna(upper):mask&=(starts.isna()|(starts<upper))
    return frame.loc[mask].copy()


def _filter_point(frame: pd.DataFrame,date_col: str,lower,upper)->pd.DataFrame:
    if frame is None or frame.empty or date_col not in frame.columns:return frame
    dates=parse_datetime_series(frame[date_col])
    mask=pd.Series(True,index=frame.index)
    if not pd.isna(lower):mask&=dates.ge(lower)
    if not pd.isna(upper):mask&=dates.lt(upper)
    return frame.loc[mask].copy()


def _filter_effective_history(frame: pd.DataFrame,start_col: str,end_col: str|None,lower,upper)->pd.DataFrame:
    """Keep only history that can affect the requested audit window."""
    if frame is None or frame.empty or start_col not in frame.columns:return frame
    if end_col and end_col in frame.columns:
        return _filter_overlap(frame,start_col,end_col,lower,upper)
    starts=parse_datetime_series(frame[start_col])
    if "employee_id" not in frame.columns:
        mask=pd.Series(True,index=frame.index)
        if not pd.isna(upper):mask&=(starts<upper)
        return frame.loc[mask].copy()
    keep=set()
    for _,group in frame.groupby(frame["employee_id"].astype(str),dropna=False):
        gd=starts.loc[group.index]
        if not pd.isna(lower):
            prior=gd[gd<=lower]
            if not prior.empty:keep.add(prior.idxmax())
        inside=pd.Series(True,index=group.index)
        if not pd.isna(lower):inside&=gd.ge(lower)
        if not pd.isna(upper):inside&=gd.lt(upper)
        keep.update(group.index[inside])
        if pd.isna(lower) and not pd.isna(upper):keep.update(group.index[gd<upper])
        if pd.isna(lower) and pd.isna(upper):keep.update(group.index)
    return frame.loc[sorted(keep)].copy() if keep else frame.iloc[0:0].copy()


def prune_frames_to_window(frames: dict[str,pd.DataFrame],start_date=None,end_date=None)->dict[str,pd.DataFrame]:
    """Return canonical frames reduced to evidence relevant to an audit window."""
    if not start_date and not end_date:return frames
    lower,upper=_range_bounds(start_date,end_date)
    out={k:(v.copy() if v is not None else pd.DataFrame()) for k,v in frames.items()}

    out["timesheets"]=_filter_overlap(out.get("timesheets",pd.DataFrame()),"start_datetime","end_datetime",lower,upper)
    out["rostered_shifts"]=_filter_overlap(out.get("rostered_shifts",pd.DataFrame()),"rostered_start_datetime","rostered_end_datetime",lower,upper)
    out["payroll_earnings"]=_filter_overlap(out.get("payroll_earnings",pd.DataFrame()),"pay_period_start","pay_period_end",lower,upper)
    out["pay_runs"]=_filter_overlap(out.get("pay_runs",pd.DataFrame()),"pay_period_start","pay_period_end",lower,upper)

    out["pay_details"]=_filter_effective_history(out.get("pay_details",pd.DataFrame()),"effective_from",None,lower,upper)
    out["employment_history"]=_filter_effective_history(out.get("employment_history",pd.DataFrame()),"start_date","end_date",lower,upper)
    out["industrial_instrument_history"]=_filter_effective_history(out.get("industrial_instrument_history",pd.DataFrame()),"effective_from","effective_to",lower,upper)
    out["part_time_patterns"]=_filter_effective_history(out.get("part_time_patterns",pd.DataFrame()),"effective_from","effective_to",lower,upper)

    out["part_time_variations"]=_filter_point(out.get("part_time_variations",pd.DataFrame()),"shift_date",lower,upper)
    out["public_holiday_overrides"]=_filter_point(out.get("public_holiday_overrides",pd.DataFrame()),"holiday_date",lower,upper)
    out["overtime_rest_controls"]=_filter_point(out.get("overtime_rest_controls",pd.DataFrame()),"shift_start",lower,upper)
    out["meal_break_events"]=_filter_point(out.get("meal_break_events",pd.DataFrame()),"scheduled_break_start",lower,upper)
    out["supplemental_events"]=_filter_overlap(out.get("supplemental_events",pd.DataFrame()),"start_datetime","end_datetime",lower,upper)
    out["toil_register"]=_filter_point(out.get("toil_register",pd.DataFrame()),"overtime_datetime",lower,upper)
    return out


def load_file_source(input_root: str|Path,start_date=None,end_date=None)->dict[str,pd.DataFrame]:
    """Load canonical file evidence and prune it to the requested audit window."""
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
    frames=prune_frames_to_window(frames,start_date,end_date)
    if frames["timesheets"].empty:
        raise ValueError(f"No timesheets fall inside the requested audit window: {start_date} to {end_date}")
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
