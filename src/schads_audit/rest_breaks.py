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
    return any(
        "OVERTIME" in str(item.get("component", "")).upper()
        for item in _evidence(value)
        if isinstance(item, dict)
    )


def _rest_rule(conditions: dict[str, Any]) -> dict[str, Any]:
    explicit = conditions.get("rest_between_work") or {}
    sleepover = conditions.get("sleepover") or {}
    return {
        "default_hours": float(explicit.get("default_hours", 10)),
        "sleepover_adjacent_agreement_hours": float(explicit.get("sleepover_adjacent_agreement_hours", 8)),
        "sleepover_adjacent_agreement_required": bool(explicit.get("sleepover_adjacent_agreement_required", True)),
        "sleepover_counts_as_break": bool(
            explicit.get("sleepover_counts_as_break", sleepover.get("sleepover_counts_as_rest_break", False))
        ),
        "surrounding_work_same_shift": bool(
            explicit.get("surrounding_work_same_shift", sleepover.get("surrounding_work_is_one_shift", False))
        ),
        "historical_sleepover_interaction_review": bool(
            explicit.get(
                "historical_sleepover_interaction_review",
                not bool(sleepover.get("surrounding_work_is_one_shift", False)),
            )
        ),
        "general_short_rest_has_automatic_pay_penalty": bool(
            explicit.get("general_short_rest_has_automatic_pay_penalty", False)
        ),
        "overtime_resume_minimum_multiplier": float(explicit.get("overtime_resume_minimum_multiplier", 2.0)),
        "overtime_resume_excludes_casual": bool(explicit.get("overtime_resume_excludes_casual", True)),
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
    if controls is None or controls.empty or "employee_id" not in controls.columns:
        return None
    q = controls[controls["employee_id"].astype(str) == str(employee_id)].copy()
    if q.empty:
        return None
    previous_ids = {str(x) for x in previous_ids if x not in (None, "")}
    next_ids = {str(x) for x in next_ids if x not in (None, "")}
    for column, values in (
        ("previous_timesheet_id", previous_ids),
        ("next_timesheet_id", next_ids),
        ("timesheet_id", next_ids),
    ):
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


def _new_unit(members, *, start=None, end=None, contains_sleepover=False, sleepover_group_id=None, broken_shift_group_id=None):
    work_members = [m for m in members if _bool(m.get("is_sleepover")) is not True]
    if not work_members:
        return None
    starts = [_dt(m.get("start_datetime")) for m in members]
    ends = [_dt(m.get("end_datetime")) for m in members]
    starts = [x for x in starts if x is not None]
    ends = [x for x in ends if x is not None]
    if not starts or not ends:
        return None
    roles = {str(m.get("sleepover_period_role") or "") for m in work_members}
    return {
        "employee_id": str(work_members[0].get("employee_id")),
        "timesheet_ids": [m.get("timesheet_id") for m in work_members],
        "start": start or min(starts),
        "end": end or max(ends),
        "sleepover_group_id": sleepover_group_id,
        "broken_shift_group_id": broken_shift_group_id,
        "contains_sleepover": bool(contains_sleepover),
        "role_before": "BEFORE" in roles,
        "role_after": "AFTER" in roles,
    }


def _work_units(timesheets, lib):
    """Build work units used for rest sequencing.

    Periods that form one broken shift are consolidated. From the 2026 sleepover
    variation, work immediately before and after a sleepover is consolidated into
    one shift. Pre-variation sleepover periods remain separate from surrounding
    work and can count as rest according to the effective condition pack.
    """
    if timesheets is None or timesheets.empty:
        return [], []
    rows = [row.to_dict() for _, row in timesheets.iterrows()]
    groups = _sleepover_groups(timesheets)
    consumed = set()
    units = []
    sleepovers = []

    for row in rows:
        if _bool(row.get("is_sleepover")) is not True:
            continue
        start = _dt(row.get("start_datetime"))
        end = _dt(row.get("end_datetime"))
        if start is None or end is None or end <= start:
            continue
        rule = _rest_rule(lib.conditions(start) or {})
        sleepovers.append(
            {
                "employee_id": str(row.get("employee_id")),
                "timesheet_id": row.get("timesheet_id"),
                "group_id": row.get("sleepover_group_id"),
                "start": start,
                "end": end,
                "counts_as_break": rule["sleepover_counts_as_break"],
            }
        )

    # Current Award treatment: the sleepover and immediately surrounding work are
    # one shift for the rest-between-work test.
    for gid, members in groups.items():
        reference = _dt(next((m.get("start_datetime") for m in members if _bool(m.get("is_sleepover")) is True), None))
        if reference is None:
            reference = _dt(members[0].get("start_datetime"))
        rule = _rest_rule(lib.conditions(reference) or {}) if reference is not None else _rest_rule({})
        if not rule["surrounding_work_same_shift"]:
            continue
        unit = _new_unit(members, contains_sleepover=True, sleepover_group_id=gid)
        if unit:
            units.append(unit)
            consumed.update(
                str(m.get("timesheet_id"))
                for m in members
                if m.get("timesheet_id") not in (None, "")
            )

    # A broken shift is a single shift made up of multiple work periods. Its
    # internal unpaid breaks are not separate 10-hour-rest events.
    broken_groups = {}
    for row in rows:
        tid = str(row.get("timesheet_id"))
        if tid in consumed or _bool(row.get("is_sleepover")) is True:
            continue
        gid = row.get("broken_shift_group_id")
        if gid:
            broken_groups.setdefault(str(gid), []).append(row)
    for gid, members in broken_groups.items():
        unit = _new_unit(members, broken_shift_group_id=gid)
        if unit:
            units.append(unit)
            consumed.update(
                str(m.get("timesheet_id"))
                for m in members
                if m.get("timesheet_id") not in (None, "")
            )

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
        unit = _new_unit(
            [row],
            sleepover_group_id=row.get("sleepover_group_id"),
            broken_shift_group_id=row.get("broken_shift_group_id"),
        )
        if unit:
            units.append(unit)

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
    return bool(
        nxt.get("contains_sleepover")
        or nxt.get("role_before")
        or previous.get("contains_sleepover")
        or previous.get("role_after")
    )


def _historical_internal_sleepover(previous, nxt, sleepovers, lib):
    gid = previous.get("sleepover_group_id")
    if not gid or str(gid) != str(nxt.get("sleepover_group_id")):
        return False
    if not previous.get("role_before") or not nxt.get("role_after"):
        return False
    matching = [s for s in sleepovers if str(s.get("group_id")) == str(gid)]
    if not matching:
        return False
    return _rest_rule(lib.conditions(previous["start"]) or {})["historical_sleepover_interaction_review"]


def _unit_detail_rows(detail, unit):
    ids = {str(x) for x in unit.get("timesheet_ids", []) if x not in (None, "")}
    if not ids:
        return detail.iloc[0:0]
    return detail[detail["timesheet_id"].astype(str).isin(ids)]


def _unit_has_overtime(detail, unit):
    rows = _unit_detail_rows(detail, unit)
    return any(
        _has_overtime(value)
        for value in rows.get("calculation_evidence", pd.Series(dtype=str))
    )


def _reprice_resumed_work_to_minimum(detail, employee_id, resume_start, release_datetime, minimum_multiplier, event_key, clause):
    """Top up observed resumed work to a minimum multiplier when unambiguous.

    Rows already containing overtime repricing are returned for review rather than
    being repriced a second time because those evidence records overlap the
    ordinary components. Multi-rate rows are calculated only when the whole row is
    inside the affected interval; a partial multi-rate row is review-only.
    """
    out = detail
    topup = Decimal("0")
    repriced_hours = 0.0
    review_flags = []
    rows = out[out["employee_id"].astype(str) == str(employee_id)]
    for idx, row in rows.iterrows():
        start = _dt(row.get("shift_start"))
        end = _dt(row.get("shift_end"))
        if start is None or end is None or end <= resume_start or start >= release_datetime:
            continue
        affected_start = max(start, resume_start)
        affected_end = min(end, release_datetime)
        affected_hours = max(0.0, (affected_end - affected_start).total_seconds() / 3600)
        if affected_hours <= 0:
            continue
        base = float(row.get("base_hourly_rate") or 0)
        if base <= 0:
            review_flags.append("REST_AFTER_OVERTIME_RATE_MISSING")
            continue
        evidence = _evidence(row.get("calculation_evidence"))
        if any(
            isinstance(item, dict)
            and "OVERTIME" in str(item.get("component", "")).upper()
            for item in evidence
        ):
            review_flags.append("REST_AFTER_OVERTIME_RESUMED_WORK_OVERTIME_INTERACTION_REVIEW")
            continue
        if any(
            isinstance(item, dict)
            and item.get("component") == "REST_AFTER_OVERTIME_DOUBLE_TIME_TOPUP"
            and item.get("rest_event_key") == event_key
            for item in evidence
        ):
            continue
        rate_items = [
            item
            for item in evidence
            if isinstance(item, dict)
            and item.get("component") == "ORDINARY_OR_PENALTY"
            and item.get("hours") not in (None, "")
            and item.get("effective_hourly_rate") is not None
        ]
        if not rate_items:
            review_flags.append("REST_AFTER_OVERTIME_REPRICE_EVIDENCE_MISSING")
            continue
        row_span = max(0.0, (end - start).total_seconds() / 3600)
        if affected_hours + 1e-6 < row_span and len(rate_items) > 1:
            review_flags.append("REST_AFTER_OVERTIME_PARTIAL_MULTIRATE_RELEASE_REVIEW")
            continue
        minimum_rate = float(effective_hourly_rate(base, minimum_multiplier))
        remaining = affected_hours
        row_topup = Decimal("0")
        for item in rate_items:
            hours = min(remaining, max(0.0, float(item.get("hours") or 0)))
            if hours <= 0:
                continue
            current_rate = float(item["effective_hourly_rate"])
            delta_rate = max(0.0, minimum_rate - current_rate)
            row_topup += line_amount(hours, delta_rate)
            remaining -= hours
            if remaining <= 1e-9:
                break
        if remaining > 1e-6:
            review_flags.append("REST_AFTER_OVERTIME_REPRICE_HOURS_UNRESOLVED")
            continue
        row_topup = money(row_topup)
        if row_topup > 0:
            out.at[idx, "expected_amount"] = float(
                money(Decimal(str(row.get("expected_amount") or 0)) + row_topup)
            )
            evidence.append(
                {
                    "component": "REST_AFTER_OVERTIME_DOUBLE_TIME_TOPUP",
                    "rest_event_key": event_key,
                    "affected_start": str(affected_start),
                    "affected_end": str(affected_end),
                    "affected_hours": round(affected_hours, 4),
                    "minimum_multiplier": minimum_multiplier,
                    "minimum_rate": minimum_rate,
                    "amount": float(row_topup),
                    "release_datetime": str(release_datetime),
                    "clause": clause,
                }
            )
            out.at[idx, "calculation_evidence"] = json.dumps(
                evidence, default=str, separators=(",", ":")
            )
            topup += row_topup
        repriced_hours += affected_hours
    review = "; ".join(sorted(set(review_flags))) if review_flags else None
    return out, float(money(topup)), round(repriced_hours, 4), review


def _rostered_absence_hours(rosters, employee_id, release_datetime, rest_hours):
    if rosters is None or rosters.empty:
        return None
    if not {
        "employee_id",
        "rostered_start_datetime",
        "rostered_end_datetime",
    }.issubset(rosters.columns):
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


def apply_rest_between_work(
    detail,
    timesheets,
    rosters,
    rest_controls,
    legacy_overtime_rest_controls,
    lib,
):
    """Audit effective-dated SCHADS rest-between-work requirements.

    A clause 25.4 rest finding is kept separate from any monetary consequence.
    Double-time under clause 28.3(b) is applied only when the preceding work
    contains overtime, the employment type is in scope, and employer instruction
    to resume or continue work is evidenced. Missing facts produce
    REQUIRES_REVIEW rather than an assumed entitlement.
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
            rule = _rest_rule(lib.conditions(reference) or {})
            actual_rest, sleepover_blockers = _qualifying_rest_hours(
                previous, nxt, sleepovers
            )
            eligible_8h = _sleepover_adjacent(previous, nxt)
            historical_internal = _historical_internal_sleepover(
                previous, nxt, sleepovers, lib
            )
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
                notes.append(
                    "Historical sleepover/rest interaction requires evidence review before a definitive clause 25.4 conclusion."
                )
            elif actual_rest >= rule["default_hours"]:
                status = "COMPLIANT"
            elif eligible_8h and actual_rest >= rule["sleepover_adjacent_agreement_hours"]:
                if agreement is True or not rule["sleepover_adjacent_agreement_required"]:
                    required = rule["sleepover_adjacent_agreement_hours"]
                    status = "COMPLIANT_AGREED_8H"
                elif agreement is False:
                    status = "NONCOMPLIANT"
                    notes.append(
                        "The sleepover-adjacent 8-hour reduction was not agreed."
                    )
                else:
                    status = "REQUIRES_REVIEW"
                    notes.append(
                        "Evidence of the employee/employer agreement for the 8-hour sleepover-adjacent exception is required."
                    )
            else:
                status = "NONCOMPLIANT"

            next_rows = _unit_detail_rows(out, nxt)
            employee_name = None
            employment_type = None
            if not next_rows.empty:
                employee_name = next_rows.iloc[0].get("employee_name")
                employment_type = str(
                    next_rows.iloc[0].get("employment_type") or ""
                )

            in_scope_employment = not (
                rule["overtime_resume_excludes_casual"]
                and employment_type == "CASUAL"
            )
            clause_28_3 = (
                _unit_has_overtime(out, previous)
                and in_scope_employment
                and actual_rest < rule["default_hours"]
            )
            instructed = _bool((control or {}).get("employer_instructed_resume"))
            release_from_control = _dt((control or {}).get("release_datetime"))
            release = release_from_control or nxt["end"]
            event_key = (
                f"REST:{employee_id}:{previous['end'].isoformat()}:"
                f"{nxt['start'].isoformat()}"
            )
            double_time_topup = 0.0
            repriced_hours = 0.0
            paid_absence_hours = None
            payment_status = "NOT_APPLICABLE"

            if clause_28_3:
                if instructed is True:
                    if release <= nxt["start"]:
                        payment_status = "REQUIRES_REVIEW"
                        status = "REQUIRES_REVIEW"
                        notes.append(
                            "Recorded release time is not after the resumed work start."
                        )
                    else:
                        out, double_time_topup, repriced_hours, reprice_review = (
                            _reprice_resumed_work_to_minimum(
                                out,
                                employee_id,
                                nxt["start"],
                                release,
                                rule["overtime_resume_minimum_multiplier"],
                                event_key,
                                f"{rule['overtime_rest_clause']}(b)",
                            )
                        )
                        paid_absence_hours = _rostered_absence_hours(
                            rosters,
                            employee_id,
                            release,
                            rule["default_hours"],
                        )
                        if reprice_review:
                            payment_status = "REQUIRES_REVIEW"
                            status = "REQUIRES_REVIEW"
                            notes.append(reprice_review)
                        else:
                            payment_status = "DOUBLE_TIME_APPLIED"
                        if release_from_control is None:
                            notes.append(
                                "Release time was not separately evidenced; observed end of resumed work was used."
                            )
                            payment_status = "REQUIRES_REVIEW"
                            status = "REQUIRES_REVIEW"
                        if paid_absence_hours is None:
                            notes.append(
                                "Roster evidence is unavailable to quantify rostered ordinary hours in the post-release rest period."
                            )
                            payment_status = "REQUIRES_REVIEW"
                            status = "REQUIRES_REVIEW"
                        elif paid_absence_hours > 0:
                            notes.append(
                                f"{paid_absence_hours:.2f} rostered ordinary hour(s) fall within the post-release rest window; their no-loss-of-pay treatment must be verified against payroll and roster evidence."
                            )
                            payment_status = "REQUIRES_REVIEW"
                            status = "REQUIRES_REVIEW"
                elif instructed is False:
                    payment_status = "NO_DOUBLE_TIME_INSTRUCTION_NOT_ESTABLISHED"
                    notes.append(
                        "Employer instruction to resume/continue work is recorded as false; clause 28.3(b) double-time was not applied."
                    )
                else:
                    payment_status = "REQUIRES_REVIEW"
                    status = "REQUIRES_REVIEW"
                    notes.append(
                        "Employer instruction to resume/continue work must be evidenced before clause 28.3(b) double-time can be calculated."
                    )

            if status in {"NONCOMPLIANT", "REQUIRES_REVIEW"} or clause_28_3:
                flag = (
                    f"REST_BETWEEN_WORK_UNDER_{required:g}H:{actual_rest:.2f}H"
                    if actual_rest < required
                    else "REST_BETWEEN_WORK_REVIEW"
                )
                for idx in next_rows.index:
                    out.at[idx, "review_flags"] = _flag(
                        out.at[idx, "review_flags"], flag
                    )
                    out.at[idx, "entitlement_status"] = "REQUIRES_REVIEW"

            findings.append(
                {
                    "finding_id": event_key,
                    "finding_type": finding_type,
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                    "previous_timesheet_ids": ";".join(
                        str(x)
                        for x in previous.get("timesheet_ids", [])
                        if x not in (None, "")
                    ),
                    "next_timesheet_ids": ";".join(
                        str(x)
                        for x in nxt.get("timesheet_ids", [])
                        if x not in (None, "")
                    ),
                    "previous_shift_end": previous["end"],
                    "next_shift_start": nxt["start"],
                    "required_rest_hours": float(required),
                    "actual_rest_hours": round(float(actual_rest), 4),
                    "rest_shortfall_hours": round(
                        max(0.0, float(required) - float(actual_rest)), 4
                    ),
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
                    "overtime_clause": (
                        rule["overtime_rest_clause"] if clause_28_3 else None
                    ),
                    "evidence_reference": (control or {}).get(
                        "evidence_reference"
                    ),
                    "notes": " ".join(notes),
                }
            )

    return out, pd.DataFrame(findings)
