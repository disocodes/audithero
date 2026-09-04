from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from time import perf_counter

import pandas as pd

from .award_scenarios import (
    FAMILY_WORK_GROUPS,
    _classification_catalog,
    _criteria_from_detail,
    _level_pay_point,
    _observed_shift_pay,
    _precompute_source_facts,
)
from .broken_sleepover import apply_broken_shift_rules, apply_sleepover_group_rules
from .part_time_patterns import apply_part_time_pattern_checks
from .rest_breaks import apply_rest_between_work
from .rest_meal import apply_meal_break_events
from .roster_overtime import apply_rostered_and_daily_overtime, allocate_period_overtime, flag_period_overtime
from .scenario_engine import build_holiday_lookup, calculate_scenario_entitlements


EMPLOYMENT_TYPES = ("FULL_TIME", "PART_TIME", "CASUAL")


def _scenario_status(detail: pd.DataFrame) -> pd.Series:
    actual = pd.to_numeric(detail["observed_shift_pay"], errors="coerce")
    variance = pd.to_numeric(detail["shift_variance_actual_minus_expected"], errors="coerce")
    review = detail["entitlement_status"].astype(str).eq("REQUIRES_REVIEW")
    status = pd.Series("CALCULATED", index=detail.index, dtype=object)
    status.loc[actual.isna() & review] = "CALCULATED_REVIEW"
    status.loc[actual.notna() & review] = "REQUIRES_REVIEW"
    comparable = actual.notna() & ~review & variance.notna()
    status.loc[comparable & variance.lt(-0.05)] = "UNDERPAID"
    status.loc[comparable & variance.gt(0.05)] = "OVERPAID"
    status.loc[comparable & variance.between(-0.05, 0.05, inclusive="both")] = "COMPLIANT"
    return status


def _run_one(
    scenario,
    *,
    employees,
    holidays,
    lib,
    timesheets_by_group,
    holiday_lookup,
    observed_pay,
    source_facts,
    rosters,
    part_time_patterns,
    part_time_variations,
    meal_break_events,
    rest_break_controls,
    overtime_rest_controls,
):
    code = scenario["code"]
    family = scenario["family"]
    level = scenario["level"]
    pay_point = scenario["pay_point"]
    work_group = scenario["work_group"]
    emp_type = scenario["employment_type"]
    scenario_id = scenario["scenario_id"]
    scenario_timesheets = timesheets_by_group[work_group]

    detail = calculate_scenario_entitlements(
        employees,
        scenario_timesheets,
        holidays,
        lib,
        classification_code=code,
        employment_type=emp_type,
        holiday_lookup=holiday_lookup,
    )
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
    detail["scenario_classification_name"] = scenario["classification_name"]
    detail["scenario_level"] = level
    detail["scenario_pay_point"] = pay_point
    detail["scenario_work_group"] = work_group
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
    detail["matches_source_work_group"] = detail["source_work_group"].fillna("").astype(str).eq(work_group)
    detail["observed_shift_pay"] = detail["timesheet_id"].astype(str).map(observed_pay)
    detail["shift_variance_actual_minus_expected"] = (
        pd.to_numeric(detail["observed_shift_pay"], errors="coerce")
        - pd.to_numeric(detail["expected_amount"], errors="coerce")
    ).round(2)
    detail["scenario_status"] = _scenario_status(detail)

    meta = {
        "scenario_id": scenario_id,
        "classification_family": family,
        "scenario_classification_code": code,
        "scenario_classification_name": scenario["classification_name"],
        "scenario_level": level,
        "scenario_pay_point": pay_point,
        "scenario_work_group": work_group,
        "scenario_employment_type": emp_type,
    }
    criteria = _criteria_from_detail(detail, meta)

    if rest is not None and not rest.empty:
        rest = rest.copy()
        for key, value in meta.items():
            rest[key] = value
        rest["criterion_group"] = "REST_AND_BREAKS"
        rest_criteria = []
        for finding in rest.to_dict("records"):
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
                "detail": str(finding),
            })
        if rest_criteria:
            criteria = pd.concat([criteria, pd.DataFrame(rest_criteria)], ignore_index=True, sort=False)
    else:
        rest = pd.DataFrame()

    return detail, criteria, rest


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
    if employees is None or employees.empty or timesheets is None or timesheets.empty:
        return {"detail": pd.DataFrame(), "criteria": pd.DataFrame(), "rest_findings": pd.DataFrame()}

    started = perf_counter()
    catalog = _classification_catalog(lib)
    if classification_codes:
        wanted = {str(x) for x in classification_codes}
        catalog = [x for x in catalog if x["classification_code"] in wanted]

    scenarios = []
    for cls in catalog:
        code = str(cls["classification_code"])
        family = str(cls.get("classification_family") or "OTHER")
        level, pay_point = _level_pay_point(code)
        for work_group in FAMILY_WORK_GROUPS.get(family, ("OTHER",)):
            for emp_type in employment_types:
                scenarios.append({
                    "scenario_id": f"{code}:{work_group}:{emp_type}",
                    "code": code,
                    "family": family,
                    "classification_name": cls.get("classification_name"),
                    "level": level,
                    "pay_point": pay_point,
                    "work_group": work_group,
                    "employment_type": emp_type,
                })

    holiday_lookup = build_holiday_lookup(holidays)
    observed_pay = _observed_shift_pay(timesheets)
    source_facts = _precompute_source_facts(timesheets, employees, pay_details, employment_history)

    work_groups = sorted({scenario["work_group"] for scenario in scenarios})
    timesheets_by_group = {}
    for group in work_groups:
        frame = timesheets.copy()
        frame["work_group"] = group
        timesheets_by_group[group] = frame

    empty = pd.DataFrame()
    shared = {
        "employees": employees,
        "holidays": holidays,
        "lib": lib,
        "timesheets_by_group": timesheets_by_group,
        "holiday_lookup": holiday_lookup,
        "observed_pay": observed_pay,
        "source_facts": source_facts,
        "rosters": rosters if rosters is not None else empty,
        "part_time_patterns": part_time_patterns if part_time_patterns is not None else empty,
        "part_time_variations": part_time_variations if part_time_variations is not None else empty,
        "meal_break_events": meal_break_events if meal_break_events is not None else empty,
        "rest_break_controls": rest_break_controls if rest_break_controls is not None else empty,
        "overtime_rest_controls": overtime_rest_controls if overtime_rest_controls is not None else empty,
    }

    cpu_count = os.cpu_count() or 1
    workers = max(1, min(4, cpu_count, len(scenarios)))
    print(
        f"Award scenario analysis: {len(scenarios)} full passes over {len(timesheets):,} filtered timesheet row(s) "
        f"using {workers} concurrent worker(s)."
    )

    all_detail = []
    all_criteria = []
    all_rest = []
    completed = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="audithero-scenario") as pool:
        future_map = {
            pool.submit(_run_one, scenario, **shared): scenario
            for scenario in scenarios
        }
        for future in as_completed(future_map):
            scenario = future_map[future]
            detail, criteria, rest = future.result()
            all_detail.append(detail)
            if criteria is not None and not criteria.empty:
                all_criteria.append(criteria)
            if rest is not None and not rest.empty:
                all_rest.append(rest)
            completed += 1
            if completed == 1 or completed % 10 == 0 or completed == len(scenarios):
                print(
                    f"Award scenarios: {completed}/{len(scenarios)} complete; "
                    f"latest={scenario['scenario_id']}; elapsed={perf_counter() - started:.1f}s"
                )

    print(f"Award scenario analysis complete in {perf_counter() - started:.1f}s")
    return {
        "detail": pd.concat(all_detail, ignore_index=True, sort=False) if all_detail else pd.DataFrame(),
        "criteria": pd.concat(all_criteria, ignore_index=True, sort=False) if all_criteria else pd.DataFrame(),
        "rest_findings": pd.concat(all_rest, ignore_index=True, sort=False) if all_rest else pd.DataFrame(),
    }
