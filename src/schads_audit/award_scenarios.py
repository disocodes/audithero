from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from .engine import calculate_entitlements
from .roster_overtime import apply_rostered_and_daily_overtime, allocate_period_overtime, flag_period_overtime
from .broken_sleepover import apply_broken_shift_rules, apply_sleepover_group_rules
from .rest_breaks import apply_rest_between_work


EMPLOYMENT_TYPES = ("FULL_TIME", "PART_TIME", "CASUAL")


def _classification_catalog(lib) -> list[dict[str, str | None]]:
    rows: dict[str, dict[str, str | None]] = {}
    for pack in lib.rate_packs:
        family = pack.get("classification_family") or "OTHER"
        for rate in pack.get("rates", []):
            code = str(rate.get("classification_code") or "").strip()
            if not code:
                continue
            existing = rows.setdefault(code, {"classification_code": code, "classification_family": family, "classification_name": rate.get("classification_name")})
            if rate.get("classification_name"):
                existing["classification_name"] = rate.get("classification_name")
    return sorted(rows.values(), key=lambda x: x["classification_code"])


def _level_pay_point(code: str):
    m = re.search(r"-L(\d+)-P(\d+)$", str(code))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _level_hint(value: Any):
    m = re.search(r"\blevel\s*(\d+)\b", str(value or ""), re.I)
    return int(m.group(1)) if m else None


def _first_shift(timesheets: pd.DataFrame, employee_id: Any):
    q = timesheets[timesheets["employee_id"].astype(str) == str(employee_id)].copy()
    if q.empty:
        return pd.NaT
    return pd.to_datetime(q["start_datetime"], errors="coerce").min()


def _effective_start(timesheets: pd.DataFrame, employee_id: Any, fallback):
    value = _first_shift(timesheets, employee_id)
    return fallback if pd.isna(value) else value


def _supplied_base_rates(pay_details: pd.DataFrame) -> dict[str, float | None]:
    if pay_details is None or pay_details.empty or "supplied_hourly_rate" not in pay_details.columns:
        return {}
    out = {}
    for eid, group in pay_details.groupby(pay_details["employee_id"].astype(str)):
        values = pd.to_numeric(group["supplied_hourly_rate"], errors="coerce").dropna()
        out[str(eid)] = None if values.empty else float(values.iloc[-1])
    return out


def _known_classifications(pay_details: pd.DataFrame) -> tuple[dict[str, str | None], dict[str, int | None]]:
    codes, hints = {}, {}
    if pay_details is None or pay_details.empty:
        return codes, hints
    for eid, group in pay_details.groupby(pay_details["employee_id"].astype(str)):
        code_values = group.get("classification_code", pd.Series(dtype=object)).dropna().astype(str)
        codes[str(eid)] = None if code_values.empty else code_values.iloc[-1]
        text_values = group.get("classification_name", pd.Series(dtype=object)).dropna().astype(str)
        hints[str(eid)] = None if text_values.empty else _level_hint(text_values.iloc[-1])
    return codes, hints


def _known_employment_types(employment_history: pd.DataFrame | None, employees: pd.DataFrame) -> dict[str, str | None]:
    result = {}
    if employment_history is not None and not employment_history.empty and "employment_type" in employment_history.columns:
        for eid, group in employment_history.groupby(employment_history["employee_id"].astype(str)):
            values = group["employment_type"].dropna().astype(str)
            result[str(eid)] = None if values.empty else values.iloc[-1]
    for _, row in employees.iterrows():
        eid = str(row.get("employee_id"))
        if not result.get(eid):
            value = row.get("employment_type_current")
            result[eid] = None if pd.isna(value) else str(value)
    return result


def _observed_shift_pay(timesheets: pd.DataFrame) -> dict[str, float]:
    if timesheets is None or timesheets.empty:
        return {}
    result = {}
    for _, row in timesheets.iterrows():
        tid = str(row.get("timesheet_id"))
        amount = pd.to_numeric(pd.Series([row.get("source_actual_amount")]), errors="coerce").iloc[0]
        if not pd.isna(amount):
            result[tid] = round(float(amount), 2)
            continue
        rate = pd.to_numeric(pd.Series([row.get("source_actual_hourly_rate")]), errors="coerce").iloc[0]
        if pd.isna(rate):
            continue
        hours = pd.to_numeric(pd.Series([row.get("units")]), errors="coerce").iloc[0]
        if pd.isna(hours):
            start = pd.to_datetime(row.get("start_datetime"), errors="coerce")
            end = pd.to_datetime(row.get("end_datetime"), errors="coerce")
            if pd.isna(start) or pd.isna(end) or end <= start:
                continue
            hours = (end - start).total_seconds() / 3600
            brk = pd.to_numeric(pd.Series([row.get("unpaid_break_minutes")]), errors="coerce").iloc[0]
            if not pd.isna(brk):
                hours -= float(brk) / 60
        result[tid] = round(float(rate) * max(0.0, float(hours)), 2)
    return result


def _flag_group(flag: str) -> str:
    upper = flag.upper()
    if "REST" in upper:
        return "REST_AND_BREAKS"
    if "MEAL" in upper or "BREAK" in upper:
        return "MEAL_BREAKS"
    if "OVERTIME" in upper or "ROSTER" in upper:
        return "OVERTIME"
    if "SLEEPOVER" in upper:
        return "SLEEPOVER"
    if "BROKEN" in upper:
        return "BROKEN_SHIFT"
    if upper.startswith("PT_") or "PART_TIME" in upper:
        return "PART_TIME"
    if "PUBLIC_HOLIDAY" in upper or "STATE_MISSING" in upper:
        return "PUBLIC_HOLIDAYS"
    if "CLASSIFICATION" in upper or "RATE" in upper:
        return "CLASSIFICATION_AND_RATE"
    return "EVIDENCE_REQUIRED"


def _criteria_from_detail(detail: pd.DataFrame, scenario_meta: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for _, row in detail.iterrows():
        base = {
            **scenario_meta,
            "timesheet_id": row.get("timesheet_id"),
            "employee_id": row.get("employee_id"),
            "employee_name": row.get("employee_name"),
            "shift_start": row.get("shift_start"),
            "shift_end": row.get("shift_end"),
            "worked_hours": row.get("worked_hours"),
            "entitlement_status": row.get("entitlement_status"),
            "review_flags": row.get("review_flags"),
        }
        rows.append({**base, "criterion_group": "CLASSIFICATION_AND_RATE", "criterion": "MINIMUM_BASE_RATE", "clause": None, "hours": row.get("worked_hours"), "multiplier": 1.0, "effective_hourly_rate": row.get("base_hourly_rate"), "criterion_amount": None, "day_type": None, "shift_type": None, "detail": "Award minimum base hourly rate for the selected classification scenario."})
        try:
            evidence = json.loads(row.get("calculation_evidence") or "[]")
        except Exception:
            evidence = []
        for item in evidence if isinstance(evidence, list) else []:
            if not isinstance(item, dict):
                continue
            component = str(item.get("component") or "OTHER")
            group = "OTHER"
            if "OVERTIME" in component:
                group = "OVERTIME"
            elif "MINIMUM_ENGAGEMENT" in component:
                group = "MINIMUM_ENGAGEMENT"
            elif "SLEEPOVER" in component:
                group = "SLEEPOVER"
            elif "BROKEN" in component:
                group = "BROKEN_SHIFT"
            elif "ORDINARY_OR_PENALTY" in component:
                group = "PENALTIES_AND_SHIFTWORK"
            elif "MEAL" in component:
                group = "MEAL_BREAKS"
            elif "ALLOWANCE" in component:
                group = "ALLOWANCES"
            rows.append({**base, "criterion_group": group, "criterion": component, "clause": item.get("clause"), "hours": item.get("hours") or item.get("affected_hours"), "multiplier": item.get("multiplier") or item.get("overtime_multiplier"), "effective_hourly_rate": item.get("effective_hourly_rate") or item.get("overtime_rate") or item.get("minimum_rate"), "criterion_amount": item.get("amount") if item.get("amount") is not None else item.get("amount_added"), "day_type": item.get("day_type"), "shift_type": item.get("shift_type"), "detail": json.dumps(item, default=str, separators=(",", ":"))})
        for flag in [x.strip() for x in str(row.get("review_flags") or "").split(";") if x.strip()]:
            rows.append({**base, "criterion_group": _flag_group(flag), "criterion": "EVIDENCE_OR_RULE_REVIEW", "clause": None, "hours": None, "multiplier": None, "effective_hourly_rate": None, "criterion_amount": None, "day_type": None, "shift_type": None, "detail": flag})
    return pd.DataFrame(rows)


def calculate_award_scenarios(
    employees: pd.DataFrame,
    timesheets: pd.DataFrame,
    holidays: pd.DataFrame,
    lib,
    *,
    pay_details: pd.DataFrame | None = None,
    employment_history: pd.DataFrame | None = None,
    rosters: pd.DataFrame | None = None,
    rest_break_controls: pd.DataFrame | None = None,
    overtime_rest_controls: pd.DataFrame | None = None,
    classification_codes: list[str] | None = None,
    employment_types: tuple[str, ...] = EMPLOYMENT_TYPES,
) -> dict[str, pd.DataFrame]:
    """Calculate selectable SCHADS classification/employment scenarios.

    Every supplied shift can be explored under each available SCHADS classification
    and employment type. This does not overwrite the definitive employee audit: it
    provides an analytical matrix when source classification or employment facts are
    missing, disputed, or intentionally being compared.
    """
    if employees is None or employees.empty or timesheets is None or timesheets.empty:
        return {"detail": pd.DataFrame(), "criteria": pd.DataFrame(), "rest_findings": pd.DataFrame()}

    catalog = _classification_catalog(lib)
    if classification_codes:
        wanted = {str(x) for x in classification_codes}
        catalog = [x for x in catalog if x["classification_code"] in wanted]
    supplied_rates = _supplied_base_rates(pay_details if pay_details is not None else pd.DataFrame())
    known_codes, level_hints = _known_classifications(pay_details if pay_details is not None else pd.DataFrame())
    known_types = _known_employment_types(employment_history, employees)
    observed_pay = _observed_shift_pay(timesheets)
    all_detail, all_criteria, all_rest = [], [], []

    earliest = pd.to_datetime(timesheets["start_datetime"], errors="coerce").min()
    for cls in catalog:
        code = str(cls["classification_code"])
        level, pay_point = _level_pay_point(code)
        for emp_type in employment_types:
            scenario_id = f"{code}:{emp_type}"
            synthetic_pay = pd.DataFrame([{"employee_id": str(row["employee_id"]), "effective_from": _effective_start(timesheets, row["employee_id"], earliest), "classification_code": code, "classification_name": cls.get("classification_name")} for _, row in employees.iterrows()])
            synthetic_history = pd.DataFrame([{"employee_id": str(row["employee_id"]), "start_date": _effective_start(timesheets, row["employee_id"], earliest), "end_date": pd.NaT, "employment_type": emp_type} for _, row in employees.iterrows()])

            detail = calculate_entitlements(employees, synthetic_history, synthetic_pay, timesheets, holidays, lib)
            detail = apply_broken_shift_rules(detail, timesheets, lib)
            detail = apply_sleepover_group_rules(detail, timesheets, lib)
            detail = apply_rostered_and_daily_overtime(detail, timesheets, holidays, lib)
            detail = allocate_period_overtime(detail, holidays, lib)
            detail = flag_period_overtime(detail)
            detail, rest = apply_rest_between_work(detail, timesheets, rosters if rosters is not None else pd.DataFrame(), rest_break_controls if rest_break_controls is not None else pd.DataFrame(), overtime_rest_controls if overtime_rest_controls is not None else pd.DataFrame(), lib)

            detail = detail.copy()
            detail["scenario_id"] = scenario_id
            detail["classification_family"] = cls.get("classification_family")
            detail["scenario_classification_code"] = code
            detail["scenario_classification_name"] = cls.get("classification_name")
            detail["scenario_level"] = level
            detail["scenario_pay_point"] = pay_point
            detail["scenario_employment_type"] = emp_type
            detail["supplied_base_hourly_rate"] = detail["employee_id"].astype(str).map(supplied_rates)
            detail["base_rate_variance"] = (pd.to_numeric(detail["supplied_base_hourly_rate"], errors="coerce") - pd.to_numeric(detail["base_hourly_rate"], errors="coerce")).round(2)
            detail["base_rate_status"] = detail["base_rate_variance"].map(lambda v: None if pd.isna(v) else "BELOW_MINIMUM" if v < -0.005 else "ABOVE_MINIMUM" if v > 0.005 else "AT_MINIMUM")
            detail["source_classification_code"] = detail["employee_id"].astype(str).map(known_codes)
            detail["source_level_hint"] = detail["employee_id"].astype(str).map(level_hints)
            detail["source_employment_type"] = detail["employee_id"].astype(str).map(known_types)
            detail["matches_source_classification"] = detail.apply(lambda r: bool(r.get("source_classification_code")) and str(r.get("source_classification_code")) == code, axis=1)
            detail["matches_source_level_hint"] = detail["source_level_hint"].map(lambda v: False if pd.isna(v) else int(v) == int(level or -1))
            detail["matches_source_employment_type"] = detail["source_employment_type"].astype(str).str.upper().str.replace(" ", "_").eq(emp_type)
            detail["observed_shift_pay"] = detail["timesheet_id"].astype(str).map(observed_pay)
            detail["shift_variance_actual_minus_expected"] = (pd.to_numeric(detail["observed_shift_pay"], errors="coerce") - pd.to_numeric(detail["expected_amount"], errors="coerce")).round(2)

            def scenario_status(row):
                actual = row.get("observed_shift_pay")
                if pd.isna(actual):
                    return "CALCULATED_REVIEW" if row.get("entitlement_status") == "REQUIRES_REVIEW" else "CALCULATED"
                if row.get("entitlement_status") == "REQUIRES_REVIEW":
                    return "REQUIRES_REVIEW"
                variance = row.get("shift_variance_actual_minus_expected")
                if pd.isna(variance):
                    return "CALCULATED"
                if float(variance) < -0.05:
                    return "UNDERPAID"
                if float(variance) > 0.05:
                    return "OVERPAID"
                return "COMPLIANT"

            detail["scenario_status"] = detail.apply(scenario_status, axis=1)
            meta = {"scenario_id": scenario_id, "classification_family": cls.get("classification_family"), "scenario_classification_code": code, "scenario_classification_name": cls.get("classification_name"), "scenario_level": level, "scenario_pay_point": pay_point, "scenario_employment_type": emp_type}
            criteria = _criteria_from_detail(detail, meta)
            if rest is not None and not rest.empty:
                rest = rest.copy()
                for key, value in meta.items():
                    rest[key] = value
                rest["criterion_group"] = "REST_AND_BREAKS"
                all_rest.append(rest)
                rest_criteria = []
                for _, finding in rest.iterrows():
                    rest_criteria.append({**meta, "timesheet_id": finding.get("next_timesheet_ids"), "employee_id": finding.get("employee_id"), "employee_name": finding.get("employee_name"), "shift_start": finding.get("next_shift_start"), "shift_end": None, "worked_hours": None, "entitlement_status": finding.get("status"), "review_flags": finding.get("notes"), "criterion_group": "REST_AND_BREAKS", "criterion": finding.get("finding_type") or "REST_BETWEEN_WORK", "clause": finding.get("clause") or finding.get("overtime_clause"), "hours": finding.get("rest_shortfall_hours"), "multiplier": 2.0 if float(finding.get("double_time_repriced_hours") or 0) > 0 else None, "effective_hourly_rate": None, "criterion_amount": finding.get("double_time_topup"), "day_type": None, "shift_type": None, "detail": json.dumps(finding.to_dict(), default=str, separators=(",", ":"))})
                if rest_criteria:
                    criteria = pd.concat([criteria, pd.DataFrame(rest_criteria)], ignore_index=True, sort=False)

            all_detail.append(detail)
            if not criteria.empty:
                all_criteria.append(criteria)

    return {
        "detail": pd.concat(all_detail, ignore_index=True, sort=False) if all_detail else pd.DataFrame(),
        "criteria": pd.concat(all_criteria, ignore_index=True, sort=False) if all_criteria else pd.DataFrame(),
        "rest_findings": pd.concat(all_rest, ignore_index=True, sort=False) if all_rest else pd.DataFrame(),
    }
