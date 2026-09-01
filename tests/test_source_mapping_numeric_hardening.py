from pathlib import Path

import pandas as pd

from schads_audit.source_mapping import generate_mapping_draft
from schads_audit.source_mapping_hardening import harden_payroll_earnings_draft


def test_yes_no_break_field_is_not_mapped_as_break_minutes(tmp_path: Path):
    pd.DataFrame([
        {
            "Entry ID": "T1",
            "Employee Number": "E1",
            "Start Time": "31-08-2026 08:00",
            "End Time": "31-08-2026 12:00",
            "Unpaid Break": "No",
        },
        {
            "Entry ID": "T2",
            "Employee Number": "E1",
            "Start Time": "01-09-2026 08:00",
            "End Time": "01-09-2026 12:00",
            "Unpaid Break": "Yes",
        },
    ]).to_csv(tmp_path / "timesheets.csv", index=False)

    draft = harden_payroll_earnings_draft(generate_mapping_draft(tmp_path), tmp_path)
    timesheets = draft["datasets"]["timesheets"]

    assert "unpaid_break_minutes" not in (timesheets.get("columns") or {})
    assert (timesheets.get("_suggestions") or {}).get("unpaid_break_minutes", {}).get("suggested_source") is None


def test_numeric_break_minutes_mapping_is_retained(tmp_path: Path):
    pd.DataFrame([
        {
            "Entry ID": "T1",
            "Employee Number": "E1",
            "Start Time": "31-08-2026 08:00",
            "End Time": "31-08-2026 12:00",
            "Break Minutes": 30,
        },
        {
            "Entry ID": "T2",
            "Employee Number": "E1",
            "Start Time": "01-09-2026 08:00",
            "End Time": "01-09-2026 12:00",
            "Break Minutes": 15,
        },
    ]).to_csv(tmp_path / "timesheets.csv", index=False)

    draft = harden_payroll_earnings_draft(generate_mapping_draft(tmp_path), tmp_path)
    timesheets = draft["datasets"]["timesheets"]

    assert (timesheets.get("columns") or {}).get("unpaid_break_minutes", {}).get("source") == "Break Minutes"
