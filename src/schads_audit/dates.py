from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

# AuditHero is designed for Australian payroll data. Ambiguous numeric dates are
# therefore interpreted day-first. ISO year-first dates and timestamps remain
# fully supported for APIs, rule packs and machine-generated data.
_DAY_FIRST_RE = re.compile(r"^\s*\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}(?:\s|T|$)")
_YEAR_FIRST_RE = re.compile(r"^\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:\s|T|$)")
_COMPACT_ISO_RE = re.compile(r"^\s*\d{8}(?:\s|T|$)")
_BLANK_DATE_TEXT = {"", "nan", "nat", "none", "null"}


def parse_datetime_value(value: Any):
    """Parse one date/datetime value using Australian day-first conventions.

    Accepted examples include:
    - ``01-02-2024`` -> 1 February 2024
    - ``01/02/2024`` -> 1 February 2024
    - ``1.2.2024`` -> 1 February 2024
    - ``2024-02-01`` -> 1 February 2024
    - ``2024-02-01T09:30:00`` -> ISO timestamp
    - textual dates such as ``1 Feb 2024``

    Ambiguous numeric dates are never interpreted month-first. Existing Python,
    pandas and Excel datetime values are preserved. Invalid values return NaT so
    readiness can surface them instead of silently changing the date.
    """
    if value is None:
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, datetime):
        return pd.Timestamp(value)
    if isinstance(value, date):
        return pd.Timestamp(value)
    try:
        if pd.isna(value):
            return pd.NaT
    except Exception:
        pass

    text = str(value).strip()
    if text.lower() in _BLANK_DATE_TEXT:
        return pd.NaT

    # ISO is explicit and should never be reinterpreted as day-first.
    if _YEAR_FIRST_RE.match(text):
        return pd.to_datetime(text, errors="coerce", yearfirst=True)

    # Common compact machine date: YYYYMMDD.
    if _COMPACT_ISO_RE.match(text):
        return pd.to_datetime(text[:8], format="%Y%m%d", errors="coerce")

    # Numeric dates used by Australian operators and CSV/XLSX exports are DMY.
    if _DAY_FIRST_RE.match(text):
        return pd.to_datetime(text, errors="coerce", dayfirst=True)

    # For non-ISO textual dates and other supported strings, prefer day-first.
    # Month names remain unambiguous, while values such as 02-03 continue to DMY.
    return pd.to_datetime(text, errors="coerce", dayfirst=True)


def parse_datetime_series(series: pd.Series) -> pd.Series:
    """Parse a Series with the same rules as :func:`parse_datetime_value`."""
    if series is None:
        return pd.Series(dtype="datetime64[ns]")
    return series.map(parse_datetime_value)


def as_date(value: Any) -> date:
    """Return a Python date using AuditHero's day-first parsing policy."""
    parsed = parse_datetime_value(value)
    if pd.isna(parsed):
        raise ValueError(f"Invalid date value: {value!r}")
    return parsed.date()


def iso_date(value: Any) -> str:
    """Normalize a supported date input to ISO YYYY-MM-DD for APIs/storage."""
    return as_date(value).isoformat()


def month_chunks(start_date, end_date):
    start = as_date(start_date)
    end = as_date(end_date)
    cur = start
    while cur <= end:
        next_month = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        chunk_end = min(end, next_month - timedelta(days=1))
        yield cur.isoformat(), chunk_end.isoformat()
        cur = chunk_end + timedelta(days=1)


def recent_window(days=45, timezone="Australia/Perth"):
    now = datetime.now(ZoneInfo(timezone)).date()
    return (now - timedelta(days=int(days))).isoformat(), now.isoformat()


def previous_calendar_month(timezone="Australia/Perth"):
    now = datetime.now(ZoneInfo(timezone)).date()
    first = now.replace(day=1)
    last = first - timedelta(days=1)
    return last.replace(day=1).isoformat(), last.isoformat()
