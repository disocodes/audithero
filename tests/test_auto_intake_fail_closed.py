from pathlib import Path

import pandas as pd

from schads_audit.auto_intake import build_auto_canonical


def test_auto_intake_does_not_assume_work_group_or_instrument(tmp_path: Path):
    pd.DataFrame([
        {
            "Employee Number": "E1",
            "Employee Name": "Example Employee",
            "Shift Date": "2026-07-01",
            "Start Time": "09:00",
            "End Time": "17:00",
            "Classification": "Unmapped internal level",
        }
    ]).to_csv(tmp_path / "timesheets.csv", index=False)

    result = build_auto_canonical(tmp_path)
    employee = result["frames"]["employees"].iloc[0]
    pay_detail = result["frames"]["pay_details"].iloc[0]
    timesheet = result["frames"]["timesheets"].iloc[0]

    assert pd.isna(employee["work_group"])
    assert pd.isna(timesheet["work_group"])
    assert pay_detail["industrial_instrument"] is None
    assert pd.isna(pay_detail["classification_code"])
    assert any("work groups" in text for text in result["metadata"]["warnings"])


def test_auto_intake_detects_complete_payroll_earnings_but_does_not_approve_treatment(tmp_path: Path):
    pd.DataFrame([
        {
            "Employee Number": "E1",
            "Employee Name": "Example Employee",
            "Shift Date": "2026-07-01",
            "Start Time": "09:00",
            "End Time": "17:00",
            "Employment Type": "Full Time",
            "Work Group": "Disability Services",
            "Classification": "Home Care Disability Level 1 Pay Point 1",
        }
    ]).to_csv(tmp_path / "timesheets.csv", index=False)

    pd.DataFrame([
        {
            "Employee Number": "E1",
            "Pay Period Start": "2026-07-01",
            "Pay Period End": "2026-07-14",
            "Pay Category": "Ordinary Hours",
            "Amount": 1000.0,
            "Hours": 20.0,
            "Rate": 50.0,
        }
    ]).to_csv(tmp_path / "payroll.csv", index=False)

    result = build_auto_canonical(tmp_path)
    payroll = result["frames"]["payroll_earnings"]

    assert len(payroll) == 1
    assert payroll.loc[0, "pay_category"] == "Ordinary Hours"
    assert payroll.loc[0, "amount"] == 1000.0
    assert result["metadata"]["payroll_earning_rows"] == 1
    assert any("approved treatment mapping" in text for text in result["metadata"]["warnings"])


def test_auto_intake_does_not_treat_incomplete_payroll_as_actual_pay(tmp_path: Path):
    pd.DataFrame([
        {
            "Employee Number": "E1",
            "Employee Name": "Example Employee",
            "Shift Date": "2026-07-01",
            "Start Time": "09:00",
            "End Time": "17:00",
        }
    ]).to_csv(tmp_path / "timesheets.csv", index=False)

    pd.DataFrame([
        {
            "Employee Number": "E1",
            "Pay Period Start": "2026-07-01",
            "Pay Period End": "2026-07-14",
            "Pay Category": "Ordinary Hours"
        }
    ]).to_csv(tmp_path / "payroll.csv", index=False)

    result = build_auto_canonical(tmp_path)
    assert "payroll_earnings" not in result["frames"]
    assert result["metadata"]["payroll_earning_rows"] == 0
