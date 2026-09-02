from __future__ import annotations

from decimal import Decimal
import json
from typing import Any

import pandas as pd

from .canonical_normalization import parse_datetime_value
from .money import effective_hourly_rate, line_amount, money


def _dt(value):
    parsed = parse_datetime_value(value)
    return None if pd.isna(parsed) else parsed


def _bool(value):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _flag(existing, flag):
    parts = [x for x in str(existing or "").split("; ") if x]
    parts.append(flag)
    return "; ".join(sorted(set(parts)))


def _evidence(value):
    try:
        parsed = json.loads(value or "[]")
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _has_overtime(value):
    return any("OVERTIME" in str(item.get("component", "")).upper() for item in _evidence(value) if isinstance(item, dict))


def _rest_rule(conditions: dict[str, Any]) -> dict[str, Any]:
    explicit = conditions.get("rest_between_work") or {}
    sleepover = conditions.get("sleepover") or {}
    return {
        "default_hours": float(explicit.get("default_hours", 10)),
        "sleepover_adjacent_agreement_hours": float(explicit.get("sleepover_adjacent_agreement_hours", 8)),
        "sleepover_adjacent_agreement_required": bool(explicit.get("sleepover_adjacent_agreement_required", True)),
        "sleepover_counts_as_break": bool(explicit.get("sleepover_counts_as_break", sleepover.get("sleepover_counts_as_rest_break", False))),
        "surrounding_work_same_shift": bool(explicit.get("surrounding_work_same_shift", sleepover.get("surrounding_work_is_one_shift", False))),
        "historical_sleepover_interaction_review": bool(explicit.get("historical_sleepover_interaction_review", not bool(sleepover.get("surrounding_work_is_one_shift", False)))),
        "clause": str(explicit.get("clause", "25.4")),
        "overtime_rest_clause": str(explicit.get("overtime_rest_clause", "28.3")),
    }


def _merge_controls(rest_controls, legacy_controls):
    frames = []
    for frame in (rest_controls, legacy_controls):
        if frame is not None and not frame.empty:
            frames.append(frame.copy())
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False).drop_duplicates()


def _matching_control(controls, employee_id, previous_ids, next_ids, next_start):
    if controls is None or controls.empty:
        return None
    q = controls[controls.get("employee_id", pd.Series(dtype=str)).astype(str) == str(employee_id)].copy()
    if q.empty:
        return None
    previous_ids = {str(x) for x in previous_ids if x not in (None, "")}
    next_ids = {str(x) for x in next_ids if x not in (None, "")}
    for column, values in (("previous_timesheet_id", previous_ids), ("next_timesheet_id", next_ids), ("timesheet_id", next_ids)):
        if column in q.columns and values:
            hit = q[q[column].astype(str).isin(values)]
            if len(hit) == 1:
                return hit.iloc[0].to_dict()
            if len(hit) > 1:
                q = hit
    if "shift_start" in q.columns and next_start is not None:
        q["_shift_start"] = q["shift_start"].map(parse_datetime_value)
        hit = q[q["_shift_start"] == next_start]
        if len(hit) == 1:
            return hit.iloc[0].to_dict()
    return q.iloc[0].to_dict() if len(q) == 1 else None


def _sleepover_groups(timesheets):
    groups = {}
    if timesheets is None or timesheets.empty:
        return groups
    for _, row in timesheets.iterrows():
        gid = row.get("sleepover_group_id")
        if gid:
            groups.setdefault(str(gid), []).append(row.to_dict())
    return groups


def _work_units(timesheets, lib):
    if timesheets is None or timesheets.empty:
        return [], []
    rows = [row.to_dict() for _, row in timesheets.iterrows()]
    groups = _sleepover_groups(timesheets)
    consumed = set()
    units = []
    sleepovers = []

    for row in rows:
        if _bool(row.get("is_sleepover")) is True:
            start = _dt(row.get("start_datetime"))
            end = _dt(row.get("end_datetime"))
            if start is not None and end is not None and end > start:
                conditions = lib.conditions(start)
                rule = _rest_rule(conditions or {})
                sleepovers.append({
                    "employee_id": str(row.get("employee_id")),
                    "timesheet_id": row.get("timesheet_id"),
                    "group_id": row.get("sleepover_group_id"),
                    "start": start,
                    "end": end,
                    "counts_as_break": rule["sleepover_counts_as_break"],
                })

    for gid, members in groups.items():
        role_map = {str(m.get("sleepover_period_role")): m for m in members}
        sleep = role_map.get("SLEEPOVER")
        before = role_map.get("BEFORE")
        after = role_map.get("AFTER")
        reference = _dt((sleep or before or after or {}).get("start_datetime"))
        conditions = lib.conditions(reference) if reference is not None else None
        rule = _rest_rule(conditions or {})
        if rule["surrounding_work_same_shift"] and (before or after):
            work_members = [x for x in (before, after) if x]
            starts = [_dt(x.get("start_datetime")) for x in work_members]
            ends = [_dt(x.get("end_datetime")) for x in work_members]
            if sleep:
                starts.append(_dt(sleep.get("start_datetime")))
                ends.append(_dt(sleep.get("end_datetime")))
            starts = [x for x in starts if x is not None]
            ends = [x for x in ends if x is not None]
            if starts and ends:
                units.append({
                    "employee_id": str(work_members[0].get("employee_id")),
                    "timesheet_ids": [x.get("timesheet_id") for x in work_members],
                    "start": min(starts),
                    "end": max(ends),
                    "sleepover_group_id": gid,
                    "contains_sleepover": bool(sleep),
                    "role_before": bool(before),
                    "role_after": bool(after),
                    "historical_sleepover_pair": False,
                })
                consumed.update(str(x.get("timesheet_id")) for x in work_members if x.get("timesheet_id") not in (None, ""))

    for row in rows:
        if _bool(row.get("is_sleepover")) is True:
            continue
        tid = str(row.get("timesheet_id"))
        if tid in consumed:
            continue
        start = _dt(row.get("start_datetime"))
        end = _dt(row.get("end_datetime"))
        if start is None or end is None or end <= start:
            continue
        role = str(row.get("sleepover_period_role") or "")
        units.append({
            "employee_id": str(row.get("employee_id")),
            "timesheet_ids": [row.get("timesheet_id")],
            "start": start,
            "end": end,
            "sleepover_group_id": row.get("sleepover_group_id"),
            "contains_sleepover": False,
            "role_before": role == "BEFORE",
            "role_after": role == "AFTER",
            "historical_sleepover_pair": False,
        })

    units.sort(key=lambda x: (x["employee_id"], x["start"], x["end"]))
    return units, sleepovers


def _qualifying_rest_hours(previous, nxt, sleepovers):
    if nxt["start"] <= previous["end"]:
        return 0.0, []
    blockers = []
    for sleep in sleepovers:
        if sleep["employee_id"] != previous["employee_id"] or sleep["counts_as_break"]:
            continue
        start = max(previous["end"], sleep["start"])
        end = min(nxt["start"], sleep["end"])
        if end > start:
            blockers.append((start, end, sleep))
    if not blockers:
        return (nxt["start"] - previous["end"]).total_seconds() / 3600, []
    blockers.sort(key=lambda item: item[0])
    merged = []
    for start, end, sleep in blockers:
        if not merged or start > merged[-1][1]:
            merged.append([start, end, [sleep]])
        else:
            merged[-1][1] = max(merged[-1][1], end)
            merged[-1][2].append(sleep)
    cursor = previous["end"]
    longest = 0.0
    used = []
    for start, end, sleeps in merged:
        longest = max(longest, (start - cursor).total_seconds() / 3600)
        cursor = max(cursor, end)
        used.extend(sleeps)
    longest = max(longest, (nxt["start"] - cursor).total_seconds() / 3600)
    return max(0.0, longest), used


def _sleepover_adjacent(previous, nxt):
    return bool(nxt.get("contains_sleepover") or nxt.get("role_before") or previous.get("contains_sleepover") or previous.get("role_after"))


def _historical_internal_sleepover(previous, nxt, sleepovers, lib):
    gid = previous.get("sleepover_group_id")
    if not gid or str(gid) != str(nxt.get("sleepover_group_id")):
        return False
    if not previous.get("role_before") or not nxt.get("role_after"):
        return False
    matching = [s for s in sleepovers if str(s.get("group_id")) == str(gid)]
    if not matching:
        return False
    conditions = lib.conditions(previous["start"])
    return _rest_rule(conditions or {})["historical_sleepover_interaction_review"]


def _unit_detail_rows(detail, unit):
    ids = {str(x) for x in unit.get("timesheet_ids", []) if x not in (None, "")}
    if not ids:
        return detail.iloc[0:0]
    return detail[detail["timesheet_id"].astype(str).isin(ids)]


def _unit_has_overtime(detail, unit):
    rows = _unit_detail_rows(detail, unit)
    return any(_has_overtime(value) for value in rows.get("calculation_evidence", pd.Series(dtype=str)))


def _reprice_resumed_work_to_double(detail, unit, release_datetime):
    out = detail
    topup = Decimal("0")
    repriced_hours = 0.0
    review = None
    for idx, row in _unit_detail_rows(out, unit).iterrows():
        start = _dt(row.get("shift_start"))
        end = _dt(row.get("shift_end"))
        if start is None or end is None or end <= start or start >= release_datetime:
            continue
        affected_end = min(end, release_datetime)
        affected_hours = max(0.0, (affected_end - start).total_seconds() / 3600)
        if affected_hours <= 0:
            continue
        base = float(row.get("base_hourly_rate") or 0)
        if base <= 0:
            review = "REST_AFTER_OVERTIME_RATE_MISSING"
            continue
        minimum_rate = float(effective_hourly_rate(base, 2.0))
        evidence = _evidence(row.get("calculation_evidence"))
        rate_items = [
            item for item in evidence
            if isinstance(item, dict)
            and item.get("hours") not in (None, "")
            and (item.get("effective_hourly_rate") is not None or item.get("overtime_rate") is not None or item.get("rate") is not None)
        ]
        if not rate_items:
            review = "REST_AFTER_OVERTIME_REPRICE_EVIDENCE_MISSING"
            continue
        total_evidence_hours = sum(max(0.0, float(item.get("hours") or 0)) for item in rate_items)
        if total_evidence_hours <= 0:
            review = "REST_AFTER_OVERTIME_REPRICE_EVIDENCE_MISSING"
            continue
        if affected_hours + 1e-6 < min(total_evidence_hours, max(0.0, (end - start).total_seconds() / 3600)) and len(rate_items) > 1:
            review = "REST_AFTER_OVERTIME_PARTIAL_MULTIRATE_RELEASE_REVIEW"
            continue
        remaining = affected_hours
        row_topup = Decimal("0")
        for item in rate_items:
            hours = min(remaining, max(0.0, float(item.get("hours") or 0)))
            if hours <= 0:
                continue
            current_rate = item.get("overtime_rate")
            if current_rate is None:
                current_rate = item.get("effective_hourly_rate")
            if current_rate is None:
                current_rate = item.get("rate")
            current_rate = float(current_rate)
            delta_rate = max(0.0, minimum_rate - current_rate)
            row_topup += line_amount(hours, delta_rate)
            remaining -= hours
            if remaining <= 1e-9:
                break
        row_topup = money(row_topup)
        if row_topup > 0:
            out.at[idx, "expected_amount"] = float(money(Decimal(str(row.get("expected_amount") or 0)) + row_topup))
            evidence.append({
                "component": "REST_AFTER_OVERTIME_DOUBLE_TIME_TOPUP",
                "affected_hours": round(affected_hours, 4),
                "minimum_rate": minimum_rate,
                "amount": float(row_topup),
                "release_datetime": str(release_datetime),
                "clause": "28.3(b)",
            })
            out.at[idx, "calculation_evidence"] = json.dumps(evidence, default=str, separators=(",", ":"))
            topup += row_topup
        repriced_hours += affected_hours
    return out, float(money(topup)), round(repriced_hours, 4), review


def _rostered_absence_hours(rosters, employee_id, release_datetime, rest_hours):
    if rosters is None or rosters.empty:
        return None
    if not {"employee_id", "rostered_start_datetime", "rostered_end_datetime"}.issubset(rosters.columns):
        return None
    q = rosters[rosters["employee_id"].astype(str) == str(employee_id)].copy()
    if q.empty:
        return 0.0
    q["_s"] = q["rostered_start_datetime"].map(parse_datetime_value)
    q["_e"] = q["rostered_end_datetime"].map(parse_datetime_value)
    rest_end = release_datetime + pd.Timedelta(hours=float(rest_hours))
    hours = 0.0
    for _, row in q.dropna(subset=["_s", "_e"]).iterrows():
        start = max(release_datetime, row["_s"])
        end = min(rest_end, row["_e"])
        if end > start:
            hours += (end - start).total_seconds() / 3600
    return round(hours, 4)


def apply_rest_between_work(detail, timesheets, rosters, rest_controls, legacy_overtime_rest_controls, lib):
    """Audit SCHADS rest-between-work requirements and clause 28.3 consequences.

    The function deliberately separates a rest compliance finding from a monetary
    consequence. Clause 25.4 short-rest findings do not automatically create a pay
    adjustment. Clause 28.3(b) double-time is calculated only when the preceding
    work contains overtime, the employee is not casual, and employer instruction
    to resume/continue work is evidenced. Unknown agreement/instruction facts are
    returned as review findings rather than inferred.
    """
    if detail is None or detail.empty or timesheets is None or timesheets.empty:
        return detail, pd.DataFrame()

    out = detail.copy()
    controls = _merge_controls(rest_controls, legacy_overtime_rest_controls)
    units, sleepovers = _work_units(timesheets, lib)
    findings = []
    by_employee = {}
    for unit in units:
        by_employee.setdefault(unit["employee_id"], []).append(unit)

    for employee_id, employee_units in by_employee.items():
        employee_units.sort(key=lambda x: x["start"])
        for previous, nxt in zip(employee_units[:-1], employee_units[1:]):
            reference = nxt["start"]
            conditions = lib.conditions(reference) or {}
            rule = _rest_rule(conditions)
            actual_rest, sleepover_blockers = _qualifying_rest_hours(previous, nxt, sleepovers)
            eligible_8h = _sleepover_adjacent(previous, nxt)
            historical_internal = _historical_internal_sleepover(previous, nxt, sleepovers, lib)
            control = _matching_control(
                controls,
                employee_id,
                previous.get("timesheet_ids", []),
                nxt.get("timesheet_ids", []),
                nxt["start"],
            )
            agreement = _bool((control or {}).get("sleepover_8h_agreement"))
            required = rule["default_hours"]
            status = "COMPLIANT"
            finding_type = "REST_BETWEEN_WORK"
            notes = []

            if historical_internal and actual_rest < rule["default_hours"]:
                status = "REQUIRES_REVIEW"
                finding_type = "HISTORICAL_SLEEPOVER_REST_INTERACTION"
                notes.append("Historical sleepover/rest interaction requires evidence review before a definitive clause 25.4 conclusion.")
            elif actual_rest >= rule["default_hours"]:
                status = "COMPLIANT"
            elif eligible_8h and actual_rest >= rule["sleepover_adjacent_agreement_hours"]:
                if agreement is True:
                    required = rule["sleepover_adjacent_agreement_hours"]
                    status = "COMPLIANT_AGREED_8H"
                elif agreement is False:
                    status = "NONCOMPLIANT"
                    notes.append("The sleepover-adjacent 8-hour reduction was not agreed.")
                else:
                    status = "REQUIRES_REVIEW"
                    notes.append("Evidence of the employee/employer agreement for the 8-hour sleepover-adjacent exception is required.")
            else:
                status = "NONCOMPLIANT"

            next_rows = _unit_detail_rows(out, nxt)
            employee_name = None
            employment_type = None
            if not next_rows.empty:
                employee_name = next_rows.iloc[0].get("employee_name")
                employment_type = str(next_rows.iloc[0].get("employment_type") or "")

            clause_28_3 = _unit_has_overtime(out, previous) and employment_type != "CASUAL" and actual_rest < 10
            instructed = _bool((control or {}).get("employer_instructed_resume"))
            release = _dt((control or {}).get("release_datetime"))
            if release is None:
                release = nxt["end"]
            double_time_topup = 0.0
            repriced_hours = 0.0
            paid_absence_hours = None
            payment_status = "NOT_APPLICABLE"

            if clause_28_3:
                if instructed is True:
                    out, double_time_topup, repriced_hours, reprice_review = _reprice_resumed_work_to_double(out, nxt, release)
                    paid_absence_hours = _rostered_absence_hours(rosters, employee_id, release, 10)
                    if reprice_review:
                        payment_status = "REQUIRES_REVIEW"
                        status = "REQUIRES_REVIEW"
                        notes.append(reprice_review)
                    else:
                        payment_status = "DOUBLE_TIME_APPLIED"
                    if paid_absence_hours is None:
                        notes.append("Roster evidence unavailable to quantify any rostered ordinary hours falling in the post-release 10-hour paid absence window.")
                        payment_status = "REQUIRES_REVIEW" if payment_status == "NOT_APPLICABLE" else payment_status
                    elif paid_absence_hours > 0:
                        notes.append(f"{paid_absence_hours:.2f} rostered hour(s) fall within the post-release 10-hour absence window; monetary treatment requires roster/pay-rate evidence review.")
                        payment_status = "REQUIRES_REVIEW"
                        status = "REQUIRES_REVIEW"
                elif instructed is False:
                    payment_status = "NO_DOUBLE_TIME_INSTRUCTION_NOT_ESTABLISHED"
                    notes.append("Employer instruction to resume/continue work is recorded as false; clause 28.3(b) double-time was not applied.")
                else:
                    payment_status = "REQUIRES_REVIEW"
                    status = "REQUIRES_REVIEW"
                    notes.append("Employer instruction to resume/continue work must be evidenced before clause 28.3(b) double-time can be calculated.")

            if status in {"NONCOMPLIANT", "REQUIRES_REVIEW"} or clause_28_3:
                flag = (
                    f"REST_BETWEEN_WORK_UNDER_{required:g}H:{actual_rest:.2f}H"
                    if actual_rest < required
                    else "REST_BETWEEN_WORK_REVIEW"
                )
                for idx in next_rows.index:
                    out.at[idx, "review_flags"] = _flag(out.at[idx, "review_flags"], flag)
                    out.at[idx, "entitlement_status"] = "REQUIRES_REVIEW"

            finding_id = f"REST:{employee_id}:{previous['end'].isoformat()}:{nxt['start'].isoformat()}"
            findings.append({
                "finding_id": finding_id,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "previous_timesheet_ids": ";".join(str(x) for x in previous.get("timesheet_ids", []) if x not in (None, "")),
                "next_timesheet_ids": ";".join(str(x) for x in nxt.get("timesheet_ids", []) if x not in (None, "")),
                "previous_shift_end": previous["end"],
                "next_shift_start": nxt["start"],
                "required_rest_hours": float(required),
                "actual_rest_hours": round(float(actual_rest), 4),
                "rest_shortfall_hours": round(max(0.0, float(required) - float(actual_rest)), 4),
                "sleepover_adjacent_exception_eligible": bool(eligible_8h),
                "sleepover_8h_agreement": agreement,
                "sleepover_blocked_rest": bool(sleepover_blockers),
                "historical_sleepover_interaction": bool(historical_internal),
                "overtime_rest_rule_applies": bool(clause_28_3),
                "employer_instructed_resume": instructed,
                "release_datetime": release if clause_28_3 else None,
                "double_time_repriced_hours": repriced_hours,
                "double_time_topup": round(float(double_time_topup), 2),
                "paid_absence_rostered_hours": paid_absence_hours,
                "payment_status": payment_status,
                "status": status,
                "clause": rule["clause"],
                "overtime_clause": rule["overtime_rest_clause"] if clause_28_3 else None,
                "evidence_reference": (control or {}).get("evidence_reference"),
                "notes": " ".join(notes),
            })

    return out, pd.DataFrame(findings)
