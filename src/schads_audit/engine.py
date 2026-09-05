from __future__ import annotations
from datetime import time
from decimal import Decimal
import json

import pandas as pd

from .money import money, effective_hourly_rate, line_amount
from .canonical_normalization import parse_datetime_series, parse_datetime_value, numeric_value


def _dt(v):
    x = parse_datetime_value(v)
    return None if pd.isna(x) else x


def _bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _emp_type(v):
    s = str(v or "").upper().replace("-", "_").replace(" ", "_")
    if "CASUAL" in s:
        return "CASUAL"
    if "PART" in s:
        return "PART_TIME"
    if "FULL" in s:
        return "FULL_TIME"
    return "UNKNOWN"


def _prepare_effective_frame(df, start_col, end_col=None):
    if df is None or df.empty:
        return df
    out = df.copy()
    out["_employee_key"] = out["employee_id"].astype(str)
    out["_s"] = parse_datetime_series(out[start_col])
    if end_col and end_col in out.columns:
        out["_e"] = parse_datetime_series(out[end_col])
    return out


def _effective_row(df, eid, at_date, start_col, end_col=None):
    if df is None or df.empty:
        return None
    employee_key = df["_employee_key"] if "_employee_key" in df.columns else df.employee_id.astype(str)
    q = df[employee_key == str(eid)]
    if q.empty:
        return None
    starts = q["_s"] if "_s" in q.columns else parse_datetime_series(q[start_col])
    at = _dt(at_date)
    if at is None:
        return None
    q = q.loc[starts <= at].copy()
    if q.empty:
        return None
    if end_col and end_col in q.columns:
        ends = q["_e"] if "_e" in q.columns else parse_datetime_series(q[end_col])
        q = q.loc[ends.isna() | (ends >= at)]
    return None if q.empty else q.sort_values("_s" if "_s" in q.columns else start_col, ascending=False).iloc[0].to_dict()


def _split(start, end, break_minutes=0):
    start = _dt(start)
    end = _dt(end)
    cuts = [start]
    midnight = start.normalize() + pd.Timedelta(days=1)
    while midnight < end:
        cuts.append(midnight)
        midnight += pd.Timedelta(days=1)
    cuts.append(end)
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        out.append({"date": a.date(), "hours": (b - a).total_seconds() / 3600})
    if len(out) == 1:
        out[0]["hours"] = max(0, out[0]["hours"] - numeric_value(break_minutes) / 60)
    return out


def _prepare_holidays(holidays):
    if holidays is None or holidays.empty:
        return holidays
    out = holidays.copy()
    out["_d"] = parse_datetime_series(out["holiday_date"]).dt.date
    out["_state"] = out["state"].astype(str).str.upper()
    return out


def _day_type(d, state, holidays, location_key=None):
    if holidays is not None and not holidays.empty:
        dates = holidays["_d"] if "_d" in holidays.columns else parse_datetime_series(holidays.holiday_date).dt.date
        states = holidays["_state"] if "_state" in holidays.columns else holidays.state.astype(str).str.upper()
        q = holidays[(dates == d) & (states == str(state).upper())]
        if not q.empty:
            if "holiday_location_key" not in q.columns:
                return "PUBLIC_HOLIDAY"

            def applies(v):
                if pd.isna(v) or str(v).strip() == "":
                    return True
                return location_key is not None and str(v) == str(location_key)

            if q["holiday_location_key"].apply(applies).any():
                return "PUBLIC_HOLIDAY"
    return "SATURDAY" if d.weekday() == 5 else "SUNDAY" if d.weekday() == 6 else "WEEKDAY"


def _shift_type(start, end):
    start = _dt(start)
    end = _dt(end)
    if start.weekday() > 4:
        return "NONE"
    if start.time() < time(6):
        return "NIGHT"
    if end.date() > start.date():
        return "NIGHT"
    if end.time() > time(20):
        return "AFTERNOON"
    return "NONE"


def _mult(c, emp_type, day_type, shift_type):
    m = float(c["ordinary_penalties"][emp_type][day_type])
    if day_type == "WEEKDAY" and shift_type in ("AFTERNOON", "NIGHT"):
        m = (1.25 if emp_type == "CASUAL" else 1.0) + float(c["shiftwork"][shift_type]["loading"])
    return m


def _minimum(c, work_group, emp_type):
    fallback = None
    for row in c["minimum_engagement"]:
        if row["work_group"] == "OTHER" and emp_type in row["employment_types"]:
            fallback = (float(row["hours"]), row["clause"])
        if row["work_group"] == work_group and emp_type in row["employment_types"]:
            return float(row["hours"]), row["clause"]
    return fallback or (0, None)


def _first_full_pay_period_transition(reference, packs, window_days=31):
    """Return True only when a missing pay-period start can change rule selection."""
    ref = _dt(reference)
    if ref is None:
        return False
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        basis = str(pack.get("application_basis") or "").strip().upper()
        if basis != "FIRST_FULL_PAY_PERIOD_START_ON_OR_AFTER":
            continue
        operative = _dt(pack.get("operative_date"))
        if operative is None:
            continue
        delta = ref.normalize() - operative.normalize()
        if pd.Timedelta(0) <= delta <= pd.Timedelta(days=window_days):
            return True
    return False


def assign_pay_periods(timesheets, pay_runs):
    df = timesheets.copy()
    df["pay_period_start"] = None
    df["pay_period_end"] = None
    df["pay_run_id"] = None
    if not pay_runs:
        return df

    def first(r, *keys):
        for key in keys:
            if isinstance(r, dict) and r.get(key) not in (None, ""):
                return r[key]

    periods = []
    for row in pay_runs:
        ps = _dt(first(row, "payPeriodStarting", "PayPeriodStarting", "payPeriodStart", "startDate"))
        pe = _dt(first(row, "payPeriodEnding", "PayPeriodEnding", "payPeriodEnd", "endDate"))
        rid = first(row, "id", "Id", "payRunId", "PayRunId")
        if ps is not None and pe is not None:
            periods.append((ps.normalize(), pe.normalize(), rid))
    for idx, row in df.iterrows():
        start = _dt(row.get("start_datetime"))
        if start is None:
            continue
        hits = [p for p in periods if p[0].date() <= start.date() <= p[1].date()]
        if len(hits) == 1:
            ps, pe, rid = hits[0]
            df.at[idx, "pay_period_start"] = ps
            df.at[idx, "pay_period_end"] = pe
            df.at[idx, "pay_run_id"] = rid
        elif len(hits) > 1:
            df.at[idx, "pay_period_mapping_status"] = "AMBIGUOUS_PAY_SCHEDULE"
    return df


def calculate_entitlements(employees, employment_history, classifications, timesheets, holidays, lib):
    if timesheets is None or timesheets.empty:
        return pd.DataFrame()
    emp_index = {str(r.employee_id): r.to_dict() for _, r in employees.iterrows()}
    employment_history = _prepare_effective_frame(employment_history, "start_date", "end_date")
    classifications = _prepare_effective_frame(classifications, "effective_from")
    holidays = _prepare_holidays(holidays)
    rows = []

    for _, ts0 in timesheets.iterrows():
        ts = ts0.to_dict()
        flags = []
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

        employment = _effective_row(employment_history, eid, start, "start_date", "end_date")
        emp_type = _emp_type((employment or {}).get("employment_type") or emp.get("employment_type_current"))
        if emp_type == "UNKNOWN":
            flags.append("EMPLOYMENT_TYPE_HISTORY_MISSING")

        classification = _effective_row(classifications, eid, start, "effective_from")
        code = (classification or {}).get("classification_code")
        if not code:
            flags.append("SCHADS_CLASSIFICATION_MAPPING_MISSING")

        pp_start = _dt(ts.get("pay_period_start"))
        reference = pp_start if pp_start is not None else start
        rate, rate_pack = lib.rate(code, reference) if code else (None, None)
        conditions = lib.conditions(reference)
        allowance_pack = lib.allowances(reference)
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
        evidence = []

        if base is not None and conditions and emp_type in ("FULL_TIME", "PART_TIME", "CASUAL"):
            if not is_sleepover:
                for segment in segments:
                    day_type = _day_type(segment["date"], state, holidays, holiday_location_key)
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
                    day_type = _day_type(segments[0]["date"], state, holidays, holiday_location_key)
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
                evidence.append({"component": "SLEEPOVER_SPAN", "span_hours": round(span_hours, 4), "ordinary_hours_paid": 0.0, "clause": "25.7"})
                allowance, selected_allowance_pack = lib.allowance("sleepover", reference)
                if allowance:
                    expected += money(allowance["amount"])
                    evidence.append({"component": "SLEEPOVER_ALLOWANCE", "amount": float(money(allowance["amount"])), "allowance_pack_id": selected_allowance_pack["allowance_pack_id"], "clause": "25.7"})
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


def reconcile_pay_periods(entitlements, payroll_lines, mapping, tolerance=0.05):
    if entitlements is None or entitlements.empty:
        return pd.DataFrame()
    expected = entitlements.copy()
    expected["expected_amount"] = pd.to_numeric(expected.expected_amount, errors="coerce")
    columns = ["employee_id", "employee_name", "pay_period_start", "pay_period_end"]
    grouped = expected.groupby(columns, dropna=False).agg(
        expected_amount=("expected_amount", "sum"),
        shift_count=("timesheet_id", "count"),
        entitlement_review_count=("entitlement_status", lambda values: int((values == "REQUIRES_REVIEW").sum())),
    ).reset_index()

    if payroll_lines is None or payroll_lines.empty:
        grouped["actual_auditable_amount"] = None
        grouped["variance_actual_minus_expected"] = None
        grouped["unmapped_pay_categories"] = "ACTUAL_PAY_UNAVAILABLE"
        grouped["status"] = "ENTITLEMENT_ONLY"
        return grouped

    payroll = payroll_lines.copy()
    payroll["pay_period_start"] = parse_datetime_series(payroll.pay_period_start)
    payroll["pay_period_end"] = parse_datetime_series(payroll.pay_period_end)
    payroll["amount"] = pd.to_numeric(payroll.amount, errors="coerce").fillna(0)

    def treatment(row):
        for key in [str(row.get("pay_category_id") or ""), str(row.get("pay_category") or "")]:
            if key in mapping:
                return mapping[key].get("audit_treatment") if isinstance(mapping[key], dict) else mapping[key]
        return "UNMAPPED"

    payroll["audit_treatment"] = payroll.apply(treatment, axis=1)
    rows = []
    for keys, group in payroll.groupby(["employee_id", "pay_period_start", "pay_period_end"], dropna=False):
        auditable = group[group.audit_treatment.isin(["AUDITABLE_WORK", "ALLOWANCE"])]
        unmapped = sorted(set(group.loc[group.audit_treatment == "UNMAPPED", "pay_category"].astype(str)))
        rows.append({"employee_id": str(keys[0]), "pay_period_start": keys[1], "pay_period_end": keys[2], "actual_auditable_amount": round(float(auditable.amount.sum()), 2), "unmapped_pay_categories": "; ".join(unmapped)})

    out = grouped.merge(pd.DataFrame(rows), on=["employee_id", "pay_period_start", "pay_period_end"], how="left")
    out["variance_actual_minus_expected"] = (pd.to_numeric(out.actual_auditable_amount, errors="coerce") - pd.to_numeric(out.expected_amount, errors="coerce")).round(2)

    def status(row):
        if int(row.entitlement_review_count) > 0 or row.get("unmapped_pay_categories"):
            return "REQUIRES_REVIEW"
        if pd.isna(row.actual_auditable_amount):
            return "ACTUAL_PAY_UNAVAILABLE"
        if row.variance_actual_minus_expected < -tolerance:
            return "UNDERPAID"
        if row.variance_actual_minus_expected > tolerance:
            return "OVERPAID"
        return "COMPLIANT"

    out["status"] = out.apply(status, axis=1)
    return out
