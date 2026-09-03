from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from .engine import calculate_entitlements
from .roster_overtime import apply_rostered_and_daily_overtime, allocate_period_overtime, flag_period_overtime
from .broken_sleepover import apply_broken_shift_rules, apply_sleepover_group_rules
from .rest_breaks import apply_rest_between_work
from .part_time_patterns import apply_part_time_pattern_checks
from .rest_meal import apply_meal_break_events


EMPLOYMENT_TYPES = ("FULL_TIME", "PART_TIME", "CASUAL")
FAMILY_WORK_GROUPS = {
    "SACS": ("SACS_NON_DISABILITY",),
    "HOME_CARE_DISABILITY": ("DISABILITY_SERVICES", "HOME_CARE"),
}


def _classification_catalog(lib) -> list[dict[str, str | None]]:
    rows: dict[str, dict[str, str | None]] = {}
    for pack in lib.rate_packs:
        family = pack.get("classification_family") or "OTHER"
        for rate in pack.get("rates", []):
            code = str(rate.get("classification_code") or "").strip()
            if not code:
                continue
            existing = rows.setdefault(
                code,
                {
                    "classification_code": code,
                    "classification_family": family,
                    "classification_name": rate.get("classification_name"),
                },
            )
            if rate.get("classification_name"):
                existing["classification_name"] = rate.get("classification_name")
    return sorted(rows.values(), key=lambda x: x["classification_code"])


def _level_pay_point(code: str):
    match = re.search(r"-L(\d+)-P(\d+)$", str(code))
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def _level_hint(value: Any):
    match = re.search(r"\blevel\s*(\d+)\b", str(value or ""), re.I)
    return int(match.group(1)) if match else None


def _first_shift(timesheets: pd.DataFrame, employee_id: Any):
    q = timesheets[timesheets["employee_id"].astype(str) == str(employee_id)].copy()
    if q.empty:
        return pd.NaT
    return pd.to_datetime(q["start_datetime"], errors="coerce").min()


def _effective_start(timesheets: pd.DataFrame, employee_id: Any, fallback):
    value = _first_shift(timesheets, employee_id)
    return fallback if pd.isna(value) else value


def _effective_record(frame: pd.DataFrame | None, employee_id: Any, when: Any, date_col: str):
    if frame is None or frame.empty or "employee_id" not in frame.columns or date_col not in frame.columns:
        return None
    at = pd.to_datetime(when, errors="coerce")
    q = frame[frame["employee_id"].astype(str) == str(employee_id)].copy()
    if q.empty:
        return None
    q["_effective"] = pd.to_datetime(q[date_col], errors="coerce")
    dated = q[q["_effective"].notna()].copy()
    if not pd.isna(at):
        dated = dated[dated["_effective"] <= at]
    if not dated.empty:
        return dated.sort_values("_effective").iloc[-1].to_dict()
    undated = q[q["_effective"].isna()]
    return undated.iloc[-1].to_dict() if not undated.empty else None


def _source_pay_facts(pay_details: pd.DataFrame | None, employee_id: Any, shift_start: Any) -> dict[str, Any]:
    record = _effective_record(pay_details, employee_id, shift_start, "effective_from")
    if not record:
        return {
            "supplied_base_hourly_rate": None,
            "source_rate_effective_from": None,
            "source_rate_reference": None,
            "source_classification_code": None,
            "source_classification_name": None,
            "source_level_hint": None,
        }
    rate = pd.to_numeric(pd.Series([record.get("supplied_hourly_rate")]), errors="coerce").iloc[0]
    return {
        "supplied_base_hourly_rate": None if pd.isna(rate) else float(rate),
        "source_rate_effective_from": record.get("effective_from"),
        "source_rate_reference": record.get("source_reference"),
        "source_classification_code": record.get("classification_code"),
        "source_classification_name": record.get("classification_name"),
        "source_level_hint": _level_hint(record.get("classification_name")),
    }


def _source_employment_type(employment_history: pd.DataFrame | None, employees: pd.DataFrame, employee_id: Any, shift_start: Any):
    record = _effective_record(employment_history, employee_id, shift_start, "start_date")
    if record and record.get("employment_type") not in (None, "", "UNKNOWN"):
        return str(record.get("employment_type"))
    q = employees[employees["employee_id"].astype(str) == str(employee_id)]
    if q.empty:
        return None
    value = q.iloc[0].get("employment_type_current")
    return None if pd.isna(value) else str(value)


def _source_work_group(timesheets: pd.DataFrame, employees: pd.DataFrame, timesheet_id: Any, employee_id: Any):
    if timesheets is not None and not timesheets.empty and "timesheet_id" in timesheets.columns:
        q = timesheets[timesheets["timesheet_id"].astype(str) == str(timesheet_id)]
        if not q.empty:
            value = q.iloc[0].get("work_group")
            if value is not None and not pd.isna(value) and str(value).strip():
                return str(value).strip()
    if employees is not None and not employees.empty:
        q = employees[employees["employee_id"].astype(str) == str(employee_id)]
        if not q.empty:
            value = q.iloc[0].get("work_group")
            if value is not None and not pd.isna(value) and str(value).strip():
                return str(value).strip()
    return None


def _observed_shift_pay(timesheets: pd.DataFrame) -> dict[str, float]:
    """Return only explicit actual shift amounts.

    A supplied base hourly rate is deliberately not multiplied by hours here. A
    base-rate file proves the employee's nominal hourly rate, not the complete
    amount paid for penalties, overtime, allowances or other Award components.
    """
    if timesheets is None or timesheets.empty or "source_actual_amount" not in timesheets.columns:
        return {}
    result = {}
    for _, row in timesheets.iterrows():
        amount = pd.to_numeric(pd.Series([row.get("source_actual_amount")]), errors="coerce").iloc[0]
        if not pd.isna(amount):
            result[str(row.get("timesheet_id"))] = round(float(amount), 2)
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
    if "CLASSIFICATION" in upper or "RATE" in upper or "WORK_GROUP" in upper:
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
        rate_variance = pd.to_numeric(pd.Series([row.get("base_rate_variance")]), errors="coerce").iloc[0]
        worked = pd.to_numeric(pd.Series([row.get("worked_hours")]), errors="coerce").iloc[0]
        base_shortfall = None
        if not pd.isna(rate_variance) and not pd.isna(worked):
            base_shortfall = round(max(0.0, -float(rate_variance)) * max(0.0, float(worked)), 2)
        rows.append({
            **base,
            "criterion_group": "CLASSIFICATION_AND_RATE",
            "criterion": "MINIMUM_BASE_RATE",
            "clause": None,
            "hours": row.get("worked_hours"),
            "multiplier": 1.0,
            "effective_hourly_rate": row.get("base_hourly_rate"),
            "criterion_amount": base_shortfall,
            "day_type": None,
            "shift_type": None,
            "detail": json.dumps({
                "award_minimum_base_rate": row.get("base_hourly_rate"),
                "supplied_base_hourly_rate": row.get("supplied_base_hourly_rate"),
                "base_rate_variance": row.get("base_rate_variance"),
                "base_rate_status": row.get("base_rate_status"),
                "source_rate_effective_from": row.get("source_rate_effective_from"),
                "source_rate_reference": row.get("source_rate_reference"),
                "scenario_work_group": row.get("scenario_work_group"),
            }, default=str, separators=(",", ":")),
        })
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
            rows.append({
                **base,
                "criterion_group": group,
                "criterion": component,
                "clause": item.get("clause"),
                "hours": item.get("hours") or item.get("affected_hours"),
                "multiplier": item.get("multiplier") or item.get("overtime_multiplier"),
                "effective_hourly_rate": item.get("effective_hourly_rate") or item.get("overtime_rate") or item.get("minimum_rate"),
                "criterion_amount": item.get("amount") if item.get("amount") is not None else item.get("amount_added"),
                "day_type": item.get("day_type"),
                "shift_type": item.get("shift_type"),
                "detail": json.dumps(item, default=str, separators=(",", ":")),
            })
        for flag in [x.strip() for x in str(row.get("review_flags") or "").split(";") if x.strip()]:
            rows.append({
                **base,
                "criterion_group": _flag_group(flag),
                "criterion": "EVIDENCE_OR_RULE_REVIEW",
                "clause": None,
                "hours": None,
                "multiplier": None,
                "effective_hourly_rate": None,
                "criterion_amount": None,
                "day_type": None,
                "shift_type": None,
                "detail": flag,
            })
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
    part_time_patterns: pd.DataFrame | None = None,
    part_time_variations: pd.DataFrame | None = None,
    meal_break_events: pd.DataFrame | None = None,
    rest_break_controls: pd.DataFrame | None = None,
    overtime_rest_controls: pd.DataFrame | None = None,
    classification_codes: list[str] | None = None,
    employment_types: tuple[str, ...] = EMPLOYMENT_TYPES,
) -> dict[str, pd.DataFrame]:
    """Calculate selectable SCHADS classification, work-area and employment scenarios."""
    if employees is None or employees.empty or timesheets is None or timesheets.empty:
        return {"detail": pd.DataFrame(), "criteria": pd.DataFrame(), "rest_findings": pd.DataFrame()}

    catalog = _classification_catalog(lib)
    if classification_codes:
        wanted = {str(x) for x in classification_codes}
        catalog = [x for x in catalog if x["classification_code"] in wanted]
    observed_pay = _observed_shift_pay(timesheets)
    all_detail, all_criteria, all_rest = [], [], []
    earliest = pd.to_datetime(timesheets["start_datetime"], errors="coerce").min()

    for cls in catalog:
        code = str(cls["classification_code"])
        family = str(cls.get("classification_family") or "OTHER")
        level, pay_point = _level_pay_point(code)
        work_groups = FAMILY_WORK_GROUPS.get(family, ("OTHER",))
        for scenario_work_group in work_groups:
            scenario_timesheets = timesheets.copy()
            scenario_timesheets["work_group"] = scenario_work_group
            for emp_type in employment_types:
                scenario_id = f"{code}:{scenario_work_group}:{emp_type}"
                synthetic_pay = pd.DataFrame([
                    {
                        "employee_id": str(row["employee_id"]),
                        "effective_from": _effective_start(timesheets, row["employee_id"], earliest),
                        "classification_code": code,
                        "classification_name": cls.get("classification_name"),
                    }
                    for _, row in employees.iterrows()
                ])
                synthetic_history = pd.DataFrame([
                    {
                        "employee_id": str(row["employee_id"]),
                        "start_date": _effective_start(timesheets, row["employee_id"], earliest),
                        "end_date": pd.NaT,
                        "employment_type": emp_type,
                    }
                    for _, row in employees.iterrows()
                ])

                detail = calculate_entitlements(employees, synthetic_history, synthetic_pay, scenario_timesheets, holidays, lib)
                detail = apply_broken_shift_rules(detail, scenario_timesheets, lib)
                detail = apply_sleepover_group_rules(detail, scenario_timesheets, lib)
                detail = apply_rostered_and_daily_overtime(detail, scenario_timesheets, holidays, lib)
                detail = allocate_period_overtime(detail, holidays, lib)
                detail = flag_period_overtime(detail)
                detail = apply_part_time_pattern_checks(
                    detail,
                    part_time_patterns if part_time_patterns is not None else pd.DataFrame(),
                    part_time_variations if part_time_variations is not None else pd.DataFrame(),
                )
                detail = apply_meal_break_events(
                    detail,
                    scenario_timesheets,
                    meal_break_events if meal_break_events is not None else pd.DataFrame(),
                    holidays,
                    lib,
                )
                detail, rest = apply_rest_between_work(
                    detail,
                    scenario_timesheets,
                    rosters if rosters is not None else pd.DataFrame(),
                    rest_break_controls if rest_break_controls is not None else pd.DataFrame(),
                    overtime_rest_controls if overtime_rest_controls is not None else pd.DataFrame(),
                    lib,
                )

                detail = detail.copy()
                detail["scenario_id"] = scenario_id
                detail["classification_family"] = family
                detail["scenario_classification_code"] = code
                detail["scenario_classification_name"] = cls.get("classification_name")
                detail["scenario_level"] = level
                detail["scenario_pay_point"] = pay_point
                detail["scenario_work_group"] = scenario_work_group
                detail["scenario_employment_type"] = emp_type

                source_rows = []
                for _, row in detail.iterrows():
                    facts = _source_pay_facts(pay_details, row.get("employee_id"), row.get("shift_start"))
                    facts["source_employment_type"] = _source_employment_type(
                        employment_history, employees, row.get("employee_id"), row.get("shift_start")
                    )
                    facts["source_work_group"] = _source_work_group(
                        timesheets, employees, row.get("timesheet_id"), row.get("employee_id")
                    )
                    source_rows.append(facts)
                source_df = pd.DataFrame(source_rows, index=detail.index)
                for column in source_df.columns:
                    detail[column] = source_df[column]

                detail["base_rate_variance"] = (
                    pd.to_numeric(detail["supplied_base_hourly_rate"], errors="coerce")
                    - pd.to_numeric(detail["base_hourly_rate"], errors="coerce")
                ).round(2)
                detail["base_rate_status"] = detail["base_rate_variance"].map(
                    lambda value: None if pd.isna(value) else "BELOW_MINIMUM" if value < -0.005 else "ABOVE_MINIMUM" if value > 0.005 else "AT_MINIMUM"
                )
                detail["matches_source_classification"] = detail.apply(
                    lambda row: bool(row.get("source_classification_code")) and str(row.get("source_classification_code")) == code,
                    axis=1,
                )
                detail["matches_source_level_hint"] = detail["source_level_hint"].map(
                    lambda value: False if pd.isna(value) else int(value) == int(level or -1)
                )
                normalized_source_type = (
                    detail["source_employment_type"].fillna("").astype(str).str.upper()
                    .str.replace(" ", "_", regex=False).str.replace("-", "_", regex=False)
                )
                detail["matches_source_employment_type"] = normalized_source_type.eq(emp_type)
                detail["matches_source_work_group"] = detail["source_work_group"].fillna("").astype(str).eq(scenario_work_group)
                detail["observed_shift_pay"] = detail["timesheet_id"].astype(str).map(observed_pay)
                detail["shift_variance_actual_minus_expected"] = (
                    pd.to_numeric(detail["observed_shift_pay"], errors="coerce")
                    - pd.to_numeric(detail["expected_amount"], errors="coerce")
                ).round(2)

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
                meta = {
                    "scenario_id": scenario_id,
                    "classification_family": family,
                    "scenario_classification_code": code,
                    "scenario_classification_name": cls.get("classification_name"),
                    "scenario_level": level,
                    "scenario_pay_point": pay_point,
                    "scenario_work_group": scenario_work_group,
                    "scenario_employment_type": emp_type,
                }
                criteria = _criteria_from_detail(detail, meta)

                if rest is not None and not rest.empty:
                    rest = rest.copy()
                    for key, value in meta.items():
                        rest[key] = value
                    rest["criterion_group"] = "REST_AND_BREAKS"
                    all_rest.append(rest)
                    rest_criteria = []
                    for _, finding in rest.iterrows():
                        rest_criteria.append({
                            **meta,
                            "timesheet_id": finding.get("next_timesheet_ids"),
                            "employee_id": finding.get("employee_id"),
                            "employee_name": finding.get("employee_name"),
                            "shift_start": finding.get("next_shift_start"),
                            "shift_end": None,
                            "worked_hours": None,
                            "entitlement_status": finding.get("status"),
                            "review_flags": finding.get("notes"),
                            "criterion_group": "REST_AND_BREAKS",
                            "criterion": finding.get("finding_type") or "REST_BETWEEN_WORK",
                            "clause": finding.get("clause") or finding.get("overtime_clause"),
                            "hours": finding.get("rest_shortfall_hours"),
                            "multiplier": 2.0 if float(finding.get("double_time_repriced_hours") or 0) > 0 else None,
                            "effective_hourly_rate": None,
                            "criterion_amount": finding.get("double_time_topup"),
                            "day_type": None,
                            "shift_type": None,
                            "detail": json.dumps(finding.to_dict(), default=str, separators=(",", ":")),
                        })
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
