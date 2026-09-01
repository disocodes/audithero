import pandas as pd

from schads_audit.canonical_normalization import (
    normalize_canonical_frame,
    numeric_value,
    parse_datetime_value,
)


def test_australian_datetime_and_iso_datetime_are_both_parsed_correctly():
    assert parse_datetime_value("31-08-2026 07:30") == pd.Timestamp("2026-08-31 07:30")
    assert parse_datetime_value("2026-08-31 07:30") == pd.Timestamp("2026-08-31 07:30")


def test_invalid_optional_numeric_value_is_flagged_instead_of_raising():
    frame = pd.DataFrame([
        {
            "timesheet_id": "T1",
            "employee_id": "E1",
            "start_datetime": "31-08-2026 08:00",
            "end_datetime": "31-08-2026 12:00",
            "unpaid_break_minutes": "No",
        }
    ])
    out = normalize_canonical_frame("timesheets", frame)
    assert pd.isna(out.loc[0, "unpaid_break_minutes"])
    assert bool(out.loc[0, "_invalid_unpaid_break_minutes"])
    assert out.loc[0, "start_datetime"] == pd.Timestamp("2026-08-31 08:00")


def test_numeric_value_returns_safe_default_for_non_numeric_text():
    assert numeric_value("No") == 0.0
    assert numeric_value("30") == 30.0
