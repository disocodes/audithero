from __future__ import annotations

from decimal import Decimal
import json
from typing import Any

import pandas as pd

from .canonical_normalization import numeric_value, parse_datetime_value
from .engine import _bool, _dt, _first_full_pay_period_transition, _minimum, _mult, _shift_type, _split
from .money import effective_hourly_rate, line_amount, money


def build_holiday_lookup(holidays: pd.DataFrame | None) -> tuple[set[tuple[Any, str]], set[tuple[Any, str, str]]]:
    """Pre-index public holidays once for all scenario passes."""
    global_days: set[tuple[Any, str]] = set()
    keyed_days: set[tuple[Any, str, str]] = set()
    if holidays is None or holidays.empty or "holiday_date" not in holidays.columns or "state" not in holidays.columns:
        return global_days, keyed_days

    dates = holidays["holiday_date"].map(parse_datetime_value)
    states = holidays["state"].fillna("").astype(str).str.upper()
    keys = holidays["holiday_location_key"] if "holiday_location_key" in holidays.columns else pd.Series(None, index=holidays.index)
    for idx in holidays.index:
        dt = dates.loc[idx]
        if pd.isna(dt):
            continue
        state = states.loc[idx]
        key = keys.loc[idx]
        if key is None or pd.isna(key) or not str(key).strip():
            global_days.add((dt.date(), state))
        else:
            keyed_days.add((dt.date(), state, str(key)))
    return global_days, keyed_days


def _day_type_fast(
    day,
    state: Any,
    holiday_location_key: Any,
    holiday_lookup: tuple[set[tuple[Any, str]], set[tuple[Any, str, str]]],
) -> str:
    global_days, keyed_days = holiday_lookup
    state_key = str(state or "").upper()
    if (day, state_key) in global_days:
        return "PUBLIC_HOLIDAY"
    if holiday_location_key is not None and not pd.isna(holiday_location_key):
        if (day, state_key, str(holiday_location_key)) in keyed_days:
            return "PUBLIC_HOLIDAY"
    return "SATURDAY" if day.weekday() == 5 else "SUNDAY" if day.weekday() == 6 else "WEEKDAY"


def calculate_scenario_entitlements(
    employees: pd.DataFrame,
    timesheets: pd.DataFrame,
    holidays: pd.DataFrame,
    lib,
    *,
    classification_code: str,
    employment_type: str,
    holiday_lookup: tuple[set[tuple[Any, str]], set[tuple[Any, str, str]]] | None = None,
) -> pd.DataFrame:
    """Fast entitlement calculation for synthetic Award scenarios.

    Scenario runs deliberately assign one classification and one employment type
    to every employee. The generic entitlement engine therefore does unnecessary
    effective-history scans for every shift. This implementation preserves the
    same calculation rules while using those scenario constants directly.
    """
    if timesheets is None or timesheets.empty:
        return pd.DataFrame()

    emp_index = {
        str(row.get("employee_id")): row
        for row in employees.to_dict("records")
    } if employees is not None and not employees.empty else {}

    holiday_lookup = holiday_lookup or build_holiday_lookup(holidays)
    emp_type = str(employment_type or "").upper().replace("-", "_").replace(" ", "_")
    code = str(classification_code or "").strip()

    rate_cache: dict[tuple[str, str], tuple[Any, Any]] = {}
    conditions_cache: dict[str, Any] = {}
    allowance_pack_cache: dict[str, Any] = {}
    sleepover_allowance_cache: dict[str, tuple[Any, Any]] = {}

    rows: list[dict[str, Any]] = []
    for ts in timesheets.to_dict("records"):
        flags: list[str] = []
        eid = str(ts.get("employee_id"))
        emp = emp_index.get(eid)
        start = _dt(ts.get("start_datetime"))
        end = _dt(ts.get("end_datetime"))
        if not emp or start is None or end is None or end <= start:
            rows.append({
                "timesheet_id": ts.get("timesheet_id"),
                "employee_id": eid,
                "entitlement_status": "REQUIRES_REVIEW",
                "review_flags": "EMPLOYEE_OR_SHIFT_INVALID",
            })
            continue

        if ts.get("pay_period_mapping_status") == "AMBIGUOUS_PAY_SCHEDULE":
            flags.append("AMBIGUOUS_PAY_SCHEDULE")
        if emp_type not in ("FULL_TIME", "PART_TIME", "CASUAL"):
            flags.append("EMPLOYMENT_TYPE_HISTORY_MISSING")
        if not code:
            flags.append("SCHADS_CLASSIFICATION_MAPPING_MISSING")

        pp_start = _dt(ts.get("pay_period_start"))
        reference = pp_start if pp_start is not None else start
        ref_key = reference.date().isoformat()
        rate_key = (code, ref_key)
        if rate_key not in rate_cache:
            rate_cache[rate_key] = lib.rate(code, reference) if code else (None, None)
        rate, rate_pack = rate_cache[rate_key]
        if ref_key not in conditions_cache:
            conditions_cache[ref_key] = lib.conditions(reference)
        if ref_key not in allowance_pack_cache:
            allowance_pack_cache[ref_key] = lib.allowances(reference)
        conditions = conditions_cache[ref_key]
        allowance_pack = allowance_pack_cache[ref_key]

        if pp_start is None and _first_full_pay_period_transition(reference, (rate_pack, conditions, allowance_pack)):
            flags.append("PAY_PERIOD_START_REQUIRED_AT_AWARD_TRANSITION")
        if not rate:
            flags.append("RATE_PACK_OR_CLASSIFICATION_MISSING")
        if not conditions:
            flags.append("CONDITION_PACK_MISSING")

        base = float(rate["base_hourly_rate"]) if rate else None
        state = ts.get("location_state") or emp.get("state")
        source_work_group = ts.get("work_group") or emp.get("work_group")
        work_group = str(source_work_group).strip() if source_work_group not in (None, "") and not pd.isna(source_work_group) else "OTHER"
        if work_group == "OTHER":
            flags.append("WORK_GROUP_MISSING_AWARD_CONDITION_REVIEW")
        holiday_location_key = ts.get("holiday_location_key")
        is_sleepover = _bool(ts.get("is_sleepover"))
        if not state:
            flags.append("STATE_MISSING_PUBLIC_HOLIDAY_CHECK_INCOMPLETE")
        if bool(ts.get("_invalid_unpaid_break_minutes", False)):
            flags.append("UNPAID_BREAK_MINUTES_INVALID")

        break_minutes = numeric_value(ts.get("unpaid_break_minutes"))
        if not break_minutes and ts.get("break_units") not in (None, ""):
            parsed_break_units = pd.to_numeric(pd.Series([ts.get("break_units")]), errors="coerce").iloc[0]
            if pd.isna(parsed_break_units):
                flags.append("BREAK_UNITS_INVALID")
            else:
                break_minutes = float(parsed_break_units) * 60

        segments = _split(start, end, break_minutes)
        span_hours = sum(segment["hours"] for segment in segments)
        worked = 0.0 if is_sleepover else span_hours
        shift_type = _shift_type(start, end)
        expected = Decimal("0")
        evidence: list[dict[str, Any]] = []

        if base is not None and conditions and emp_type in ("FULL_TIME", "PART_TIME", "CASUAL"):
            if not is_sleepover:
                for segment in segments:
                    day_type = _day_type_fast(segment["date"], state, holiday_location_key, holiday_lookup)
                    multiplier = _mult(conditions, emp_type, day_type, shift_type)
                    effective_rate = effective_hourly_rate(base, multiplier)
                    amount = line_amount(segment["hours"], effective_rate)
                    expected += amount
                    evidence.append({
                        "component": "ORDINARY_OR_PENALTY",
                        "date": str(segment["date"]),
                        "hours": round(segment["hours"], 4),
                        "day_type": day_type,
                        "shift_type": shift_type,
                        "base_rate": base,
                        "multiplier": multiplier,
                        "effective_hourly_rate": float(effective_rate),
                        "amount": float(amount),
                        "rate_pack_id": rate_pack["rate_pack_id"],
                        "holiday_location_key": holiday_location_key,
                    })
                minimum_hours, clause = _minimum(conditions, work_group, emp_type)
                if minimum_hours and worked < minimum_hours:
                    day_type = _day_type_fast(segments[0]["date"], state, holiday_location_key, holiday_lookup)
                    multiplier = _mult(conditions, emp_type, day_type, shift_type)
                    effective_rate = effective_hourly_rate(base, multiplier)
                    extra = minimum_hours - worked
                    amount = line_amount(extra, effective_rate)
                    expected += amount
                    evidence.append({
                        "component": "MINIMUM_ENGAGEMENT_TOPUP",
                        "hours": extra,
                        "amount": float(amount),
                        "clause": clause,
                    })
            else:
                evidence.append({
                    "component": "SLEEPOVER_SPAN",
                    "span_hours": round(span_hours, 4),
                    "ordinary_hours_paid": 0.0,
                    "clause": "25.7",
                })
                if ref_key not in sleepover_allowance_cache:
                    sleepover_allowance_cache[ref_key] = lib.allowance("sleepover", reference)
                allowance, selected_allowance_pack = sleepover_allowance_cache[ref_key]
                if allowance:
                    expected += money(allowance["amount"])
                    evidence.append({
                        "component": "SLEEPOVER_ALLOWANCE",
                        "amount": float(money(allowance["amount"])),
                        "allowance_pack_id": selected_allowance_pack["allowance_pack_id"],
                        "clause": "25.7",
                    })
                else:
                    flags.append("SLEEPOVER_ALLOWANCE_MISSING")
                if bool(ts.get("_invalid_sleepover_active_minutes", False)):
                    flags.append("SLEEPOVER_ACTIVE_MINUTES_INVALID")
                if numeric_value(ts.get("sleepover_active_minutes")) > 0:
                    flags.append("SLEEPOVER_ACTIVE_WORK_NEEDS_SEPARATE_RECORD")
                if conditions["sleepover"].get("surrounding_work_is_one_shift") and not ts.get("sleepover_group_id"):
                    flags.append("SLEEPOVER_2026_CONTINUOUS_SHIFT_GROUPING_MISSING")

            if not is_sleepover and worked > float(conditions["meal_break"]["review_if_shift_gt_hours_and_no_break"]) and break_minutes == 0:
                flags.append("MEAL_BREAK_REVIEW")

        rows.append({
            "timesheet_id": ts.get("timesheet_id"),
            "employee_id": eid,
            "employee_name": emp.get("employee_name"),
            "employment_type": emp_type,
            "classification_code": code,
            "work_group": work_group,
            "state": state,
            "holiday_location_key": holiday_location_key,
            "pay_period_start": pp_start,
            "pay_period_end": _dt(ts.get("pay_period_end")),
            "award_reference_date": reference,
            "shift_start": start,
            "shift_end": end,
            "worked_hours": round(worked, 4),
            "sleepover_span_hours": round(span_hours, 4) if is_sleepover else 0.0,
            "base_hourly_rate": base,
            "expected_amount": float(money(expected)) if base is not None and conditions else None,
            "entitlement_status": "REQUIRES_REVIEW" if flags else "CALCULATED",
            "review_flags": "; ".join(sorted(set(flags))),
            "calculation_evidence": json.dumps(evidence, default=str, separators=(",", ":")),
        })

    return pd.DataFrame(rows)
