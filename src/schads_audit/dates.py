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

    if _YEAR_FIRST_RE.match(text):
        return pd.to_datetime(text, errors="coerce", yearfirst=True)
    if _COMPACT_ISO_RE.match(text):
        return pd.to_datetime(text[:8], format="%Y%m%d", errors="coerce")
    if _DAY_FIRST_RE.match(text):
        return pd.to_datetime(text, errors="coerce", dayfirst=True)
    return pd.to_datetime(text, errors="coerce", dayfirst=True)


def parse_datetime_series(series: pd.Series) -> pd.Series:
    """Vectorised Australian date parsing for dataframe columns.

    This function is intentionally column-oriented. The previous implementation
    called :func:`parse_datetime_value` once per cell, which became a major
    performance regression after date normalisation was applied throughout the
    audit engine. Pandas 2.x ``format='mixed'`` keeps ISO/machine timestamps and
    Australian day-first operator/file dates in one fast vectorised conversion.

    Examples such as ``01-05-2025`` are therefore interpreted as 1 May 2025,
    while ``2025-05-01`` remains 1 May 2025.
    """
    if series is None:
        return pd.Series(dtype="datetime64[ns]")
    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return pd.to_datetime(series, errors="coerce")

    # Pandas >=2.0 supports mixed-format vectorised parsing. dayfirst=True only
    # resolves ambiguous numeric dates; explicit year-first ISO remains year-first.
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=True)
    except (TypeError, ValueError):
        # Compatibility fallback for older pandas environments. Still operate in
        # vectorised groups rather than calling pd.to_datetime once per value.
        text = series.astype("string").str.strip()
        out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
        blank = text.str.lower().isin(_BLANK_DATE_TEXT) | text.isna()
        year_first = text.str.match(_YEAR_FIRST_RE, na=False)
        compact = text.str.match(_COMPACT_ISO_RE, na=False)
        day_first = text.str.match(_DAY_FIRST_RE, na=False)

        if year_first.any():
            out.loc[year_first] = pd.to_datetime(text.loc[year_first], errors="coerce", yearfirst=True)
        if compact.any():
            out.loc[compact] = pd.to_datetime(text.loc[compact].str.slice(0, 8), format="%Y%m%d", errors="coerce")
        dmy = day_first & ~year_first & ~compact
        if dmy.any():
            out.loc[dmy] = pd.to_datetime(text.loc[dmy], errors="coerce", dayfirst=True)
        other = ~(blank | year_first | compact | day_first)
        if other.any():
            out.loc[other] = pd.to_datetime(text.loc[other], errors="coerce", dayfirst=True)
        return out


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
