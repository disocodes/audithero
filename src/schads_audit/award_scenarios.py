from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value
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


def _blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    return not str(value).strip()


def _effective_index(frame: pd.DataFrame | None, date_col: str) -> dict[str, pd.DataFrame]:
    """Index effective-dated source facts once instead of rescanning per scenario row."""
    if frame is None or frame.empty or "employee_id" not in frame.columns or date_col not in frame.columns:
        return {}
    data = frame.copy()
    data["_employee_key"] = data["employee_id"].astype(str)
    data["_effective"] = parse_datetime_series(data[date_col])
    return {
        str(employee_id): group.sort_values("_effective", na_position="last").copy()
        for employee_id, group in data.groupby("_employee_key", dropna=False)
    }


def _effective_record_indexed(index: dict[str, pd.DataFrame], employee_id: Any, when: Any):
    group = index.get(str(employee_id))
    if group is None or group.empty:
        return None
    at = parse_datetime_value(when)
    dated = group[group["_effective"].notna()]
    if not pd.isna(at):
        dated = dated[dated["_effective"] <= at]
    if not dated.empty:
        return dated.iloc[-1].to_dict()
    undated = group[group["_effective"].isna()]
    return undated.iloc[-1].to_dict() if not undated.empty else None


def _source_pay_facts_from_record(record: dict[str, Any] | None) -> dict[str, Any]:
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


def _precompute_source_facts(
    timesheets: pd.DataFrame,
    employees: pd.DataFrame,
    pay_details: pd.DataFrame | None,
    employment_history: pd.DataFrame | None,
) -> pd.DataFrame:
    """Build scenario-invariant source facts once per supplied timesheet."""
    pay_index = _effective_index(pay_details, "effective_from")
    employment_index = _effective_index(employment_history, "start_date")

    employee_type: dict[str, Any] = {}
    employee_group: dict[str, Any] = {}
    if employees is not None and not employees.empty and "employee_id" in employees.columns:
        for _, row in employees.iterrows():
            key = str(row.get("employee_id"))
            employee_type[key] = row.get("employment_type_current")
            employee_group[key] = row.get("work_group")

    rows: list[dict[str, Any]] = []
    for _, row in timesheets.iterrows():
        employee_id = row.get("employee_id")
        employee_key = str(employee_id)
        shift_start = row.get("start_datetime")
        facts = _source_pay_facts_from_record(_effective_record_indexed(pay_index, employee_id, shift_start))

        employment = _effective_record_indexed(employment_index, employee_id, shift_start)
        employment_type = employment.get("employment_type") if employment else None
        if employment_type in (None, "", "UNKNOWN") or _blank(employment_type):
            fallback = employee_type.get(employee_key)
            employment_type = None if _blank(fallback) else str(fallback)
        else:
            employment_type = str(employment_type)

        work_group = row.get("work_group")
        if _blank(work_group):
            work_group = employee_group.get(employee_key)
        work_group = None if _blank(work_group) else str(work_group).strip()

        rows.append({
            "_timesheet_key": str(row.get("timesheet_id")),
            **facts,
            "source_employment_type": employment_type,
            "source_work_group": work_group,
        })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates("_timesheet_key", keep="last").set_index("_timesheet_key")


def _observed_shift_pay(timesheets: pd.DataFrame) -> dict[str, float]:
    """Return only explicit actual shift amounts."""
    if timesheets is None or timesheets.empty or "source_actual_amount" not in timesheets.columns:
        return {}
    amounts = pd.to_numeric(timesheets["source_actual_amount"], errors="coerce")
    keys = timesheets.get("timesheet_id", pd.Series(index=timesheets.index, dtype=object)).astype(str)
    return {key: round(float(amount), 2) for key, amount in zip(keys, amounts) if not pd.isna(amount)}


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
    """Calculate all selectable SCHADS scenarios for the already-filtered audit window.

    Audit scope is unchanged. Performance comes from computing scenario-invariant
    source facts and employee setup once rather than repeating them for every
    classification/work-group/employment-type pass.
    """
    if employees is None or employees.empty or timesheets is None or timesheets.empty:
        return {"detail": pd.DataFrame(), "criteria": pd.DataFrame(), "rest_findings": pd.DataFrame()}

    started = perf_counter()
    catalog = _classification_catalog(lib)
    if classification_codes:
        wanted = {str(x) for x in classification_codes}
        catalog = [x for x in catalog if x["classification_code"] in wanted]

    observed_pay = _observed_shift_pay(timesheets)
    source_facts = _precompute_source_facts(timesheets, employees, pay_details, employment_history)
    all_detail: list[pd.DataFrame] = []
    all_criteria: list[pd.DataFrame] = []
    all_rest: list[pd.DataFrame] = []

    starts = parse_datetime_series(timesheets["start_datetime"])
    earliest = starts.min()
    first_shift_by_employee = (
        pd.DataFrame({"employee_id": timesheets["employee_id"].astype(str), "shift_start": starts})
        .groupby("employee_id", dropna=False)["shift_start"]
        .min()
        .to_dict()
    )
    employee_keys = employees["employee_id"].astype(str)
    effective_starts = employee_keys.map(first_shift_by_employee)
    if not pd.isna(earliest):
        effective_starts = effective_starts.fillna(earliest)

    pay_seed = pd.DataFrame({"employee_id": employee_keys, "effective_from": effective_starts})
    history_seed = pd.DataFrame({
        "employee_id": employee_keys,
        "start_date": effective_starts,
        "end_date": pd.NaT,
    })

    all_work_groups = sorted({
        group
        for cls in catalog
        for group in FAMILY_WORK_GROUPS.get(str(cls.get("classification_family") or "OTHER"), ("OTHER",))
    })
    timesheets_by_group: dict[str, pd.DataFrame] = {}
    for group in all_work_groups:
        scenario_timesheets = timesheets.copy()
        scenario_timesheets["work_group"] = group
        timesheets_by_group[group] = scenario_timesheets

    scenario_total = sum(
        len(FAMILY_WORK_GROUPS.get(str(cls.get("classification_family") or "OTHER"), ("OTHER",))) * len(employment_types)
        for cls in catalog
    )
    print(f"Award scenario analysis: {scenario_total} full scenario passes over {len(timesheets):,} filtered timesheet row(s).")
    scenario_number = 0

    empty = pd.DataFrame()
    rosters = rosters if rosters is not None else empty
    part_time_patterns = part_time_patterns if part_time_patterns is not None else empty
    part_time_variations = part_time_variations if part_time_variations is not None else empty
    meal_break_events = meal_break_events if meal_break_events is not None else empty
    rest_break_controls = rest_break_controls if rest_break_controls is not None else empty
    overtime_rest_controls = overtime_rest_controls if overtime_rest_controls is not None else empty

    for cls in catalog:
        code = str(cls["classification_code"])
        family = str(cls.get("classification_family") or "OTHER")
        level, pay_point = _level_pay_point(code)
        work_groups = FAMILY_WORK_GROUPS.get(family, ("OTHER",))

        synthetic_pay = pay_seed.copy()
        synthetic_pay["classification_code"] = code
        synthetic_pay["classification_name"] = cls.get("classification_name")

        for scenario_work_group in work_groups:
            scenario_timesheets = timesheets_by_group[scenario_work_group]
            for emp_type in employment_types:
                scenario_number += 1
                scenario_id = f"{code}:{scenario_work_group}:{emp_type}"
                if scenario_number == 1 or scenario_number % 10 == 0 or scenario_number == scenario_total:
                    elapsed = perf_counter() - started
                    print(f"Award scenarios: pass {scenario_number}/{scenario_total} ({scenario_id}); elapsed {elapsed:.1f}s")

                synthetic_history = history_seed.copy()
                synthetic_history["employment_type"] = emp_type

                detail = calculate_entitlements(employees, synthetic_history, synthetic_pay, scenario_timesheets, holidays, lib)
                detail = apply_broken_shift_rules(detail, scenario_timesheets, lib)
                detail = apply_sleepover_group_rules(detail, scenario_timesheets, lib)
                detail = apply_rostered_and_daily_overtime(detail, scenario_timesheets, holidays, lib)
                detail = allocate_period_overtime(detail, holidays, lib)
                detail = flag_period_overtime(detail)
                detail = apply_part_time_pattern_checks(detail, part_time_patterns, part_time_variations)
                detail = apply_meal_break_events(detail, scenario_timesheets, meal_break_events, holidays, lib)
                detail, rest = apply_rest_between_work(
                    detail,
                    scenario_timesheets,
                    rosters,
                    rest_break_controls,
                    overtime_rest_controls,
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

                if not source_facts.empty and "timesheet_id" in detail.columns:
                    keys = detail["timesheet_id"].astype(str)
                    for column in source_facts.columns:
                        detail[column] = keys.map(source_facts[column])
                else:
                    for column in (
                        "supplied_base_hourly_rate", "source_rate_effective_from", "source_rate_reference",
                        "source_classification_code", "source_classification_name", "source_level_hint",
                        "source_employment_type", "source_work_group",
                    ):
                        detail[column] = None

                detail["base_rate_variance"] = (
                    pd.to_numeric(detail["supplied_base_hourly_rate"], errors="coerce")
                    - pd.to_numeric(detail["base_hourly_rate"], errors="coerce")
                ).round(2)
                variance = detail["base_rate_variance"]
                detail["base_rate_status"] = pd.Series(None, index=detail.index, dtype=object)
                detail.loc[variance.notna() & variance.lt(-0.005), "base_rate_status"] = "BELOW_MINIMUM"
                detail.loc[variance.notna() & variance.gt(0.005), "base_rate_status"] = "ABOVE_MINIMUM"
                detail.loc[variance.notna() & variance.between(-0.005, 0.005, inclusive="both"), "base_rate_status"] = "AT_MINIMUM"

                source_codes = detail["source_classification_code"]
                detail["matches_source_classification"] = source_codes.notna() & source_codes.astype(str).eq(code)
                hints = pd.to_numeric(detail["source_level_hint"], errors="coerce")
                detail["matches_source_level_hint"] = hints.notna() & hints.eq(float(level or -1))
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

                actual = pd.to_numeric(detail["observed_shift_pay"], errors="coerce")
                shift_variance = pd.to_numeric(detail["shift_variance_actual_minus_expected"], errors="coerce")
                review = detail["entitlement_status"].astype(str).eq("REQUIRES_REVIEW")
                status = pd.Series("CALCULATED", index=detail.index, dtype=object)
                status.loc[actual.isna() & review] = "CALCULATED_REVIEW"
                status.loc[actual.notna() & review] = "REQUIRES_REVIEW"
                comparable = actual.notna() & ~review & shift_variance.notna()
                status.loc[comparable & shift_variance.lt(-0.05)] = "UNDERPAID"
                status.loc[comparable & shift_variance.gt(0.05)] = "OVERPAID"
                status.loc[comparable & shift_variance.between(-0.05, 0.05, inclusive="both")] = "COMPLIANT"
                detail["scenario_status"] = status

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

    elapsed = perf_counter() - started
    print(f"Award scenario analysis complete: {scenario_total} passes in {elapsed:.1f}s")
    return {
        "detail": pd.concat(all_detail, ignore_index=True, sort=False) if all_detail else pd.DataFrame(),
        "criteria": pd.concat(all_criteria, ignore_index=True, sort=False) if all_criteria else pd.DataFrame(),
        "rest_findings": pd.concat(all_rest, ignore_index=True, sort=False) if all_rest else pd.DataFrame(),
    }
