from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

from .file_source import load_file_source
from .public_holidays import australian_public_holidays
from .engine import calculate_entitlements, reconcile_pay_periods
from .roster_overtime import attach_rosters, apply_rostered_and_daily_overtime, allocate_period_overtime, flag_period_overtime
from .broken_sleepover import group_broken_shifts, apply_broken_shift_rules, group_sleepovers, apply_sleepover_group_rules
from .supplemental import calculate_supplemental_events, merge_event_adjustments_into_entitlements
from .remote_work import aggregate_remote_work_events
from .industrial_instruments import apply_instrument_history
from .part_time_patterns import apply_part_time_pattern_checks
from .rest_meal import apply_rest_after_overtime, apply_meal_break_events
from .toil import audit_toil_register, merge_toil_adjustments


def _csv(path: Path):
    if not path.exists(): return pd.DataFrame()
    try: return pd.read_csv(path)
    except pd.errors.EmptyDataError: return pd.DataFrame()


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _assign_manual_pay_periods(timesheets: pd.DataFrame, pay_runs: pd.DataFrame):
    """Fill missing pay-period dates from a canonical manual pay-runs table.

    If multiple pay runs overlap the same shift date, the period remains unassigned
    so the core engine can flag the historical Award-version ambiguity.
    """
    if timesheets.empty or pay_runs is None or pay_runs.empty:
        return timesheets
    required={"pay_period_start","pay_period_end"}
    if not required.issubset(pay_runs.columns):
        return timesheets
    out=timesheets.copy()
    if "pay_period_start" not in out.columns: out["pay_period_start"]=None
    if "pay_period_end" not in out.columns: out["pay_period_end"]=None
    if "pay_run_id" not in out.columns: out["pay_run_id"]=None
    runs=pay_runs.copy()
    runs["_s"]=pd.to_datetime(runs["pay_period_start"],errors="coerce")
    runs["_e"]=pd.to_datetime(runs["pay_period_end"],errors="coerce")
    for idx,row in out.iterrows():
        if pd.notna(row.get("pay_period_start")) and str(row.get("pay_period_start")).strip():
            continue
        shift=pd.to_datetime(row.get("start_datetime"),errors="coerce")
        if pd.isna(shift): continue
        hits=runs[(runs["_s"].dt.date<=shift.date())&(runs["_e"].dt.date>=shift.date())]
        if len(hits)==1:
            r=hits.iloc[0]
            out.at[idx,"pay_period_start"]=r["pay_period_start"]
            out.at[idx,"pay_period_end"]=r["pay_period_end"]
            if "pay_run_id" in r: out.at[idx,"pay_run_id"]=r.get("pay_run_id")
    return out


def run_manual_audit(input_root, config_root, start_date, end_date, rule_library, variance_tolerance=0.05):
    """Run AuditHero from canonical CSV/XLSX inputs with no Employment Hero credentials."""
    frames=load_file_source(input_root,start_date,end_date)
    root=Path(config_root)
    employees=frames["employees"].copy()
    pay_details=frames["pay_details"].copy()
    employment_history=frames["employment_history"].copy()
    timesheets=_assign_manual_pay_periods(frames["timesheets"].copy(),frames["pay_runs"].copy())
    rosters=frames["rostered_shifts"].copy()
    payroll=frames["payroll_earnings"].copy()

    if not rosters.empty:
        timesheets=attach_rosters(timesheets,rosters)
    timesheets=group_sleepovers(timesheets)
    timesheets=group_broken_shifts(timesheets)

    holidays=pd.DataFrame(australian_public_holidays(start_date,end_date))
    override=_csv(root/"public_holiday_overrides.csv")
    if not override.empty:
        holidays=pd.concat([holidays,override],ignore_index=True,sort=False)

    detail=calculate_entitlements(employees,employment_history,pay_details,timesheets,holidays,rule_library)
    detail=apply_broken_shift_rules(detail,timesheets,rule_library)
    detail=apply_sleepover_group_rules(detail,timesheets,rule_library)
    detail=apply_rostered_and_daily_overtime(detail,timesheets,holidays,rule_library)
    detail=allocate_period_overtime(detail,holidays,rule_library)
    detail=flag_period_overtime(detail)
    detail=apply_part_time_pattern_checks(detail,_csv(root/"part_time_patterns.csv"),_csv(root/"part_time_variations.csv"))
    detail=apply_meal_break_events(detail,timesheets,_csv(root/"meal_break_events.csv"),holidays,rule_library)
    detail=apply_rest_after_overtime(detail,_csv(root/"overtime_rest_controls.csv"))
    detail=apply_instrument_history(detail,_csv(root/"industrial_instrument_history.csv"))

    events=aggregate_remote_work_events(_csv(root/"supplemental_events.csv"))
    adjustments=calculate_supplemental_events(events,employees,pay_details,holidays,rule_library)
    recon_input=merge_event_adjustments_into_entitlements(detail,adjustments)
    toil=audit_toil_register(_csv(root/"toil_register.csv"),employees,pay_details,holidays,rule_library,audit_end_date=end_date)
    recon_input=merge_toil_adjustments(recon_input,toil)
    reconciliation=reconcile_pay_periods(recon_input,payroll,_json(root/"pay_category_mapping.json"),variance_tolerance)

    return {
        "employees":employees,
        "pay_details":pay_details,
        "employment_history":employment_history,
        "timesheets":timesheets,
        "rostered_shifts":rosters,
        "payroll_earnings":payroll,
        "public_holidays":holidays,
        "detail":detail,
        "event_adjustments":adjustments,
        "toil_findings":toil,
        "reconciliation":reconciliation,
    }
