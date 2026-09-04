import pandas as pd

from schads_audit.dates import as_date, iso_date, month_chunks, parse_datetime_value
from schads_audit.canonical_normalization import normalize_canonical_frame


def test_ambiguous_numeric_dates_are_day_first():
    assert parse_datetime_value("02-03-2024") == pd.Timestamp("2024-03-02")
    assert parse_datetime_value("02/03/2024") == pd.Timestamp("2024-03-02")
    assert parse_datetime_value("2.3.2024") == pd.Timestamp("2024-03-02")


def test_day_first_datetime_with_time_is_supported():
    assert parse_datetime_value("31-01-2024 14:30") == pd.Timestamp("2024-01-31 14:30")
    assert parse_datetime_value("31/01/2024 14:30:15") == pd.Timestamp("2024-01-31 14:30:15")


def test_iso_dates_and_timestamps_keep_year_first_meaning():
    assert parse_datetime_value("2024-03-02") == pd.Timestamp("2024-03-02")
    assert parse_datetime_value("2024-03-02T14:30:00") == pd.Timestamp("2024-03-02 14:30:00")
    assert parse_datetime_value("20240302") == pd.Timestamp("2024-03-02")


def test_textual_dates_are_supported():
    assert parse_datetime_value("2 Mar 2024") == pd.Timestamp("2024-03-02")


def test_invalid_dates_fail_closed():
    assert pd.isna(parse_datetime_value("31-02-2024"))
    assert pd.isna(parse_datetime_value("not a date"))


def test_date_helpers_accept_day_first_inputs():
    assert as_date("02-03-2024").isoformat() == "2024-03-02"
    assert iso_date("02/03/2024") == "2024-03-02"
    assert list(month_chunks("15-01-2024", "05-03-2024")) == [
        ("2024-01-15", "2024-01-31"),
        ("2024-02-01", "2024-02-29"),
        ("2024-03-01", "2024-03-05"),
    ]


def test_canonical_timesheets_use_day_first_policy():
    frame = pd.DataFrame({
        "timesheet_id": ["T1"],
        "employee_id": ["E1"],
        "start_datetime": ["02-03-2024 09:00"],
        "end_datetime": ["02-03-2024 17:00"],
        "pay_period_start": ["26-02-2024"],
        "pay_period_end": ["10-03-2024"],
    })
    result = normalize_canonical_frame("timesheets", frame)
    assert result.loc[0, "start_datetime"] == pd.Timestamp("2024-03-02 09:00")
    assert result.loc[0, "end_datetime"] == pd.Timestamp("2024-03-02 17:00")
    assert result.loc[0, "pay_period_start"] == pd.Timestamp("2024-02-26")
    assert result.loc[0, "pay_period_end"] == pd.Timestamp("2024-03-10")
