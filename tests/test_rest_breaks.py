import json

import pandas as pd

from schads_audit.rest_breaks import apply_rest_between_work


class FakeRules:
    def __init__(self, *, post_2026=False):
        self.post_2026 = post_2026

    def conditions(self, reference):
        return {
            "rest_between_work": {
                "default_hours": 10,
                "sleepover_adjacent_agreement_hours": 8,
                "sleepover_adjacent_agreement_required": True,
                "sleepover_counts_as_break": not self.post_2026,
                "surrounding_work_same_shift": self.post_2026,
                "historical_sleepover_interaction_review": not self.post_2026,
                "general_short_rest_has_automatic_pay_penalty": False,
                "overtime_resume_minimum_multiplier": 2.0,
                "overtime_resume_excludes_casual": True,
                "clause": "25.4",
                "overtime_rest_clause": "28.3",
            },
            "sleepover": {
                "sleepover_counts_as_rest_break": not self.post_2026,
                "surrounding_work_is_one_shift": self.post_2026,
            },
        }


def _timesheets(first_end="2026-08-01T22:00:00", second_start="2026-08-02T08:00:00", **second):
    rows = [
        {
            "timesheet_id": "T1",
            "employee_id": "E1",
            "start_datetime": "2026-08-01T14:00:00",
            "end_datetime": first_end,
            "is_sleepover": False,
        },
        {
            "timesheet_id": "T2",
            "employee_id": "E1",
            "start_datetime": second_start,
            "end_datetime": "2026-08-02T16:00:00",
            "is_sleepover": False,
            **second,
        },
    ]
    return pd.DataFrame(rows)


def _detail(*, employment_type="FULL_TIME", previous_overtime=False):
    previous = [
        {
            "component": "ORDINARY_OR_PENALTY",
            "hours": 8,
            "effective_hourly_rate": 30.0,
        }
    ]
    if previous_overtime:
        previous.append(
            {
                "component": "DAILY_OVERTIME_REPRICE",
                "hours": 1,
                "overtime_rate": 45.0,
            }
        )
    current = [
        {
            "component": "ORDINARY_OR_PENALTY",
            "hours": 8,
            "effective_hourly_rate": 30.0,
        }
    ]
    return pd.DataFrame(
        [
            {
                "timesheet_id": "T1",
                "employee_id": "E1",
                "employee_name": "Employee One",
                "employment_type": employment_type,
                "shift_start": pd.Timestamp("2026-08-01T14:00:00"),
                "shift_end": pd.Timestamp("2026-08-01T22:00:00"),
                "base_hourly_rate": 30.0,
                "expected_amount": 240.0,
                "entitlement_status": "CALCULATED",
                "review_flags": "",
                "calculation_evidence": json.dumps(previous),
            },
            {
                "timesheet_id": "T2",
                "employee_id": "E1",
                "employee_name": "Employee One",
                "employment_type": employment_type,
                "shift_start": pd.Timestamp("2026-08-02T08:00:00"),
                "shift_end": pd.Timestamp("2026-08-02T16:00:00"),
                "base_hourly_rate": 30.0,
                "expected_amount": 240.0,
                "entitlement_status": "CALCULATED",
                "review_flags": "",
                "calculation_evidence": json.dumps(current),
            },
        ]
    )


def _roster_outside_window():
    return pd.DataFrame(
        [
            {
                "employee_id": "E1",
                "rostered_start_datetime": "2026-08-04T09:00:00",
                "rostered_end_datetime": "2026-08-04T17:00:00",
            }
        ]
    )


def test_exact_ten_hour_rest_is_compliant():
    detail, findings = apply_rest_between_work(
        _detail(), _timesheets(), _roster_outside_window(), pd.DataFrame(), pd.DataFrame(), FakeRules(post_2026=True)
    )
    assert len(findings) == 1
    assert findings.iloc[0]["actual_rest_hours"] == 10
    assert findings.iloc[0]["status"] == "COMPLIANT"
    assert findings.iloc[0]["double_time_topup"] == 0
    assert detail.iloc[1]["entitlement_status"] == "CALCULATED"


def test_general_short_rest_is_compliance_finding_not_automatic_pay_penalty():
    detail, findings = apply_rest_between_work(
        _detail(),
        _timesheets(second_start="2026-08-02T07:00:00"),
        _roster_outside_window(),
        pd.DataFrame(),
        pd.DataFrame(),
        FakeRules(post_2026=True),
    )
    finding = findings.iloc[0]
    assert finding["actual_rest_hours"] == 9
    assert finding["rest_shortfall_hours"] == 1
    assert finding["status"] == "NONCOMPLIANT"
    assert finding["payment_status"] == "NOT_APPLICABLE"
    assert finding["double_time_topup"] == 0
    assert detail.iloc[1]["entitlement_status"] == "REQUIRES_REVIEW"


def test_sleepover_adjacent_eight_hour_exception_requires_agreement():
    ts = _timesheets(
        second_start="2026-08-02T06:30:00",
        sleepover_period_role="BEFORE",
        sleepover_group_id="S1",
    )
    control = pd.DataFrame(
        [
            {
                "employee_id": "E1",
                "next_timesheet_id": "T2",
                "sleepover_8h_agreement": True,
                "evidence_reference": "AGREEMENT-1",
            }
        ]
    )
    _, findings = apply_rest_between_work(
        _detail(), ts, _roster_outside_window(), control, pd.DataFrame(), FakeRules(post_2026=False)
    )
    finding = findings.iloc[0]
    assert finding["actual_rest_hours"] == 8.5
    assert finding["required_rest_hours"] == 8
    assert finding["status"] == "COMPLIANT_AGREED_8H"
    assert finding["evidence_reference"] == "AGREEMENT-1"


def test_sleepover_adjacent_exception_without_agreement_is_review():
    ts = _timesheets(
        second_start="2026-08-02T06:30:00",
        sleepover_period_role="BEFORE",
        sleepover_group_id="S1",
    )
    _, findings = apply_rest_between_work(
        _detail(), ts, _roster_outside_window(), pd.DataFrame(), pd.DataFrame(), FakeRules(post_2026=False)
    )
    assert findings.iloc[0]["status"] == "REQUIRES_REVIEW"
    assert findings.iloc[0]["required_rest_hours"] == 10


def test_overtime_resume_with_instruction_is_topped_up_to_double_time():
    controls = pd.DataFrame(
        [
            {
                "employee_id": "E1",
                "next_timesheet_id": "T2",
                "employer_instructed_resume": True,
                "release_datetime": "2026-08-02T16:00:00",
                "evidence_reference": "DIRECTION-1",
            }
        ]
    )
    detail, findings = apply_rest_between_work(
        _detail(previous_overtime=True),
        _timesheets(second_start="2026-08-02T06:00:00"),
        _roster_outside_window(),
        controls,
        pd.DataFrame(),
        FakeRules(post_2026=True),
    )
    finding = findings.iloc[0]
    assert finding["overtime_rest_rule_applies"]
    assert finding["payment_status"] == "DOUBLE_TIME_APPLIED"
    assert finding["double_time_repriced_hours"] == 8
    assert finding["double_time_topup"] == 240
    assert detail.loc[detail.timesheet_id == "T2", "expected_amount"].iloc[0] == 480


def test_overtime_resume_without_instruction_evidence_does_not_invent_money():
    _, findings = apply_rest_between_work(
        _detail(previous_overtime=True),
        _timesheets(second_start="2026-08-02T06:00:00"),
        _roster_outside_window(),
        pd.DataFrame(),
        pd.DataFrame(),
        FakeRules(post_2026=True),
    )
    finding = findings.iloc[0]
    assert finding["overtime_rest_rule_applies"]
    assert finding["status"] == "REQUIRES_REVIEW"
    assert finding["payment_status"] == "REQUIRES_REVIEW"
    assert finding["double_time_topup"] == 0


def test_casual_short_rest_does_not_apply_clause_28_3_double_time():
    _, findings = apply_rest_between_work(
        _detail(employment_type="CASUAL", previous_overtime=True),
        _timesheets(second_start="2026-08-02T06:00:00"),
        _roster_outside_window(),
        pd.DataFrame(),
        pd.DataFrame(),
        FakeRules(post_2026=True),
    )
    finding = findings.iloc[0]
    assert finding["status"] == "NONCOMPLIANT"
    assert not finding["overtime_rest_rule_applies"]
    assert finding["double_time_topup"] == 0


def test_periods_inside_same_broken_shift_are_one_work_unit():
    timesheets = pd.DataFrame(
        [
            {
                "timesheet_id": "T1A",
                "employee_id": "E1",
                "start_datetime": "2026-08-01T08:00:00",
                "end_datetime": "2026-08-01T10:00:00",
                "broken_shift_group_id": "B1",
                "is_sleepover": False,
            },
            {
                "timesheet_id": "T1B",
                "employee_id": "E1",
                "start_datetime": "2026-08-01T16:00:00",
                "end_datetime": "2026-08-01T20:00:00",
                "broken_shift_group_id": "B1",
                "is_sleepover": False,
            },
            {
                "timesheet_id": "T2",
                "employee_id": "E1",
                "start_datetime": "2026-08-02T06:00:00",
                "end_datetime": "2026-08-02T14:00:00",
                "is_sleepover": False,
            },
        ]
    )
    detail = pd.DataFrame(
        [
            {
                "timesheet_id": tid,
                "employee_id": "E1",
                "employee_name": "Employee One",
                "employment_type": "FULL_TIME",
                "shift_start": pd.Timestamp(start),
                "shift_end": pd.Timestamp(end),
                "base_hourly_rate": 30.0,
                "expected_amount": 60.0,
                "entitlement_status": "CALCULATED",
                "review_flags": "",
                "calculation_evidence": json.dumps([{"component":"ORDINARY_OR_PENALTY","hours":2,"effective_hourly_rate":30.0}]),
            }
            for tid, start, end in (
                ("T1A", "2026-08-01T08:00:00", "2026-08-01T10:00:00"),
                ("T1B", "2026-08-01T16:00:00", "2026-08-01T20:00:00"),
                ("T2", "2026-08-02T06:00:00", "2026-08-02T14:00:00"),
            )
        ]
    )
    _, findings = apply_rest_between_work(
        detail, timesheets, _roster_outside_window(), pd.DataFrame(), pd.DataFrame(), FakeRules(post_2026=True)
    )
    assert len(findings) == 1
    assert findings.iloc[0]["previous_timesheet_ids"] == "T1A;T1B"
    assert findings.iloc[0]["actual_rest_hours"] == 10
    assert findings.iloc[0]["status"] == "COMPLIANT"
