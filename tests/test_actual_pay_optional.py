from pathlib import Path

import pandas as pd

from schads_audit.file_readiness import assess_file_readiness
from schads_audit.manual_audit import _usable_actual_pay


def _write_minimum_core(root: Path) -> None:
    pd.DataFrame([{"employee_id": "E1", "employee_name": "Ada Example"}]).to_csv(root / "employees.csv", index=False)
    pd.DataFrame([{"employee_id": "E1", "effective_from": "2026-07-01", "classification_code": "SACS-L2-P3"}]).to_csv(root / "pay_details.csv", index=False)
    pd.DataFrame([{"employee_id": "E1", "start_date": "2024-01-01", "employment_type": "CASUAL"}]).to_csv(root / "employment_history.csv", index=False)
    pd.DataFrame([{
        "timesheet_id": "T1",
        "employee_id": "E1",
        "start_datetime": "2026-08-01 08:00:00",
        "end_datetime": "2026-08-01 12:00:00",
    }]).to_csv(root / "timesheets.csv", index=False)


def test_incomplete_actual_pay_is_review_not_blocking(tmp_path: Path):
    _write_minimum_core(tmp_path)
    pd.DataFrame([{
        "employee_id": "E1",
        "pay_period_start": "2026-08-01",
        "pay_period_end": "2026-08-14",
        "amount": 1200.0,
    }]).to_csv(tmp_path / "payroll_earnings.csv", index=False)

    findings = assess_file_readiness(tmp_path, tmp_path)
    actual = findings[(findings["finding_type"] == "ACTUAL_PAY") & (findings["source_key"] == "payroll_earnings")]

    assert len(actual) == 1
    assert actual.iloc[0]["status"] == "REVIEW"
    assert "pay_category" in actual.iloc[0]["detail"]


def test_actual_pay_requires_category_and_treatment_mapping():
    incomplete = pd.DataFrame([{
        "employee_id": "E1",
        "pay_period_start": "2026-08-01",
        "pay_period_end": "2026-08-14",
        "amount": 1200.0,
    }])
    complete = incomplete.assign(pay_category="Ordinary Hours")

    assert _usable_actual_pay(incomplete, {"Ordinary Hours": {"audit_treatment": "AUDITABLE_WORK"}}) is False
    assert _usable_actual_pay(complete, {}) is False
    assert _usable_actual_pay(complete, {"Ordinary Hours": {"audit_treatment": "AUDITABLE_WORK"}}) is True
