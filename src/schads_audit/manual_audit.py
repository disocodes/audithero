from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

from .file_source import load_file_source
from .canonical_normalization import normalize_canonical_frames
from .public_holidays import australian_public_holidays
from .engine import calculate_entitlements, reconcile_pay_periods
from .roster_overtime import attach_rosters, apply_rostered_and_daily_overtime, allocate_period_overtime, flag_period_overtime
from .broken_sleepover import group_broken_shifts, apply_broken_shift_rules, group_sleepovers, apply_sleepover_group_rules
from .supplemental import calculate_supplemental_events, merge_event_adjustments_into_entitlements
from .remote_work import aggregate_remote_work_events
from .industrial_instruments import apply_instrument_history
from .part_time_patterns import apply_part_time_pattern_checks
from .rest_meal import apply_meal_break_events
from .rest_breaks import apply_rest_between_work
from .toil import audit_toil_register, merge_toil_adjustments
from .award_scenarios import calculate_award_scenarios


def _csv(path: Path):
    if not path.exists(): return pd.DataFrame()
    try: return pd.read_csv(path)
    except pd.errors.EmptyDataError: return pd.DataFrame()


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _control(frames, name, root):
    df=frames.get(name)
    return df.copy() if df is not None and not df.empty else _csv(Path(root)/f"{name}.csv")


def _pay_category_mapping(frames, root):
    df=frames.get("pay_category_mapping")
    if df is None or df.empty:
        return _json(Path(root)/"pay_category_mapping.json")
    mapping={}
    for _,r in df.iterrows():
        treatment=str(r.get("audit_treatment") or r.get("treatment") or "").strip().upper()
        if treatment not in {"AUDITABLE_WORK","ALLOWANCE","EXCLUDE"}: continue
        value={"audit_treatment":treatment}
        for key in (r.get("pay_category_id"),r.get("pay_category"),r.get("source_key"),r.get("source_label")):
            if pd.notna(key) and str(key).strip(): mapping[str(key).strip()]=value
    return mapping


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().str.lower().isin({"","nan","nat","none"})


def _mapped_treatment(row, mapping: dict):
    for key in (row.get("pay_category_id"), row.get("pay_category")):
        if pd.notna(key) and str(key).strip() in mapping:
            value=mapping[str(key).strip()]
            treatment=value.get("audit_treatment") if isinstance(value,dict) else value
            if str(treatment or "").strip().upper() in {"AUDITABLE_WORK","ALLOWANCE","EXCLUDE"}:
                return str(treatment).strip().upper()
    return None


def _usable_actual_pay(payroll: pd.DataFrame, mapping: dict, employee_ids=None) -> bool:
    """Return True only for complete, joinable and fully controlled payroll evidence."""
    if payroll is None or payroll.empty or not mapping: return False
    required={"employee_id","pay_period_start","pay_period_end","pay_category","amount"}
    if not required.issubset(payroll.columns): return False
    if any(bool(_blank(payroll[field]).any()) for field in required): return False
    if pd.to_numeric(payroll["amount"],errors="coerce").isna().any(): return False
    if employee_ids is not None:
        allowed={str(x).strip() for x in employee_ids if str(x).strip()}
        actual=set(payroll["employee_id"].astype(str).str.strip())
        if not actual.issubset(allowed): return False
    if payroll.apply(lambda row:_mapped_treatment(row,mapping),axis=1).isna().any(): return False
    return True


def _assign_manual_pay_periods(timesheets: pd.DataFrame,pay_runs: pd.DataFrame):
    if timesheets.empty or pay_runs is None or pay_runs.empty: return timesheets
    if not {"pay_period_start","pay_period_end"}.issubset(pay_runs.columns): return timesheets
    out=timesheets.copy()
    if "pay_period_start" not in out.columns: out["pay_period_start"]=None
    if "pay_period_end" not in out.columns: out["pay_period_end"]=None
    if "pay_run_id" not in out.columns: out["pay_run_id"]=None
    runs=pay_runs.copy(); runs["_s"]=pd.to_datetime(runs["pay_period_start"],errors="coerce"); runs["_e"]=pd.to_datetime(runs["pay_period_end"],errors="coerce")
    for idx,row in out.iterrows():
        if pd.notna(row.get("pay_period_start")) and str(row.get("pay_period_start")).strip(): continue
        shift=pd.to_datetime(row.get("start_datetime"),errors="coerce")
        if pd.isna(shift): continue
        hits=runs[(runs["_s"].dt.date<=shift.date())&(runs["_e"].dt.date>=shift.date())]
        if len(hits)==1:
            r=runs.loc[hits.index[0]]; out.at[idx,"pay_period_start"]=r["pay_period_start"]; out.at[idx,"pay_period_end"]=r["pay_period_end"]
            if "pay_run_id" in r: out.at[idx,"pay_run_id"]=r.get("pay_run_id")
    return out


def run_manual_audit(input_root,config_root,start_date,end_date,rule_library,variance_tolerance=0.05,generate_award_scenarios=True):
    """Run the complete file audit plus selectable SCHADS Award scenarios."""
    frames=normalize_canonical_frames(load_file_source(input_root,start_date,end_date)); root=Path(config_root)
    employees=frames["employees"].copy(); pay_details=frames["pay_details"].copy(); employment_history=frames["employment_history"].copy()
    timesheets=_assign_manual_pay_periods(frames["timesheets"].copy(),frames["pay_runs"].copy()); rosters=frames["rostered_shifts"].copy(); payroll=frames["payroll_earnings"].copy()
    if not rosters.empty: timesheets=attach_rosters(timesheets,rosters)
    timesheets=group_sleepovers(timesheets); timesheets=group_broken_shifts(timesheets)

    holidays=pd.DataFrame(australian_public_holidays(start_date,end_date)); override=_control(frames,"public_holiday_overrides",root)
    if not override.empty: holidays=pd.concat([holidays,override],ignore_index=True,sort=False)

    part_time_patterns=_control(frames,"part_time_patterns",root); part_time_variations=_control(frames,"part_time_variations",root)
    meal_break_events=_control(frames,"meal_break_events",root); rest_break_controls=_control(frames,"rest_break_controls",root); overtime_rest_controls=_control(frames,"overtime_rest_controls",root)

    detail=calculate_entitlements(employees,employment_history,pay_details,timesheets,holidays,rule_library)
    detail=apply_broken_shift_rules(detail,timesheets,rule_library); detail=apply_sleepover_group_rules(detail,timesheets,rule_library)
    detail=apply_rostered_and_daily_overtime(detail,timesheets,holidays,rule_library); detail=allocate_period_overtime(detail,holidays,rule_library); detail=flag_period_overtime(detail)
    detail=apply_part_time_pattern_checks(detail,part_time_patterns,part_time_variations)
    detail=apply_meal_break_events(detail,timesheets,meal_break_events,holidays,rule_library)
    detail,rest_findings=apply_rest_between_work(detail,timesheets,rosters,rest_break_controls,overtime_rest_controls,rule_library)
    detail=apply_instrument_history(detail,_control(frames,"industrial_instrument_history",root))

    events=aggregate_remote_work_events(_control(frames,"supplemental_events",root)); adjustments=calculate_supplemental_events(events,employees,pay_details,holidays,rule_library)
    recon_input=merge_event_adjustments_into_entitlements(detail,adjustments)
    toil=audit_toil_register(_control(frames,"toil_register",root),employees,pay_details,holidays,rule_library,audit_end_date=end_date); recon_input=merge_toil_adjustments(recon_input,toil)

    pay_mapping=_pay_category_mapping(frames,root)
    employee_ids=set(employees.get("employee_id",pd.Series(dtype=object)).dropna().astype(str).str.strip())
    actual_pay_usable=_usable_actual_pay(payroll,pay_mapping,employee_ids)
    reconciliation=reconcile_pay_periods(recon_input,payroll if actual_pay_usable else pd.DataFrame(),pay_mapping if actual_pay_usable else {},variance_tolerance)

    scenarios={"detail":pd.DataFrame(),"criteria":pd.DataFrame(),"rest_findings":pd.DataFrame()}
    if generate_award_scenarios:
        scenarios=calculate_award_scenarios(employees,timesheets,holidays,rule_library,pay_details=pay_details,employment_history=employment_history,rosters=rosters,part_time_patterns=part_time_patterns,part_time_variations=part_time_variations,meal_break_events=meal_break_events,rest_break_controls=rest_break_controls,overtime_rest_controls=overtime_rest_controls)

    return {"employees":employees,"pay_details":pay_details,"employment_history":employment_history,"timesheets":timesheets,"rostered_shifts":rosters,"payroll_earnings":payroll,"actual_pay_usable":actual_pay_usable,"public_holidays":holidays,"detail":detail,"rest_break_findings":rest_findings,"event_adjustments":adjustments,"toil_findings":toil,"reconciliation":reconciliation,"award_scenario_detail":scenarios["detail"],"award_criteria_detail":scenarios["criteria"],"award_scenario_rest_findings":scenarios["rest_findings"]}
