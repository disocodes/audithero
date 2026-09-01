from __future__ import annotations

import re
from typing import Any

import pandas as pd


# Canonical file fields that must have stable runtime types before Award modules run.
DATE_FIELDS: dict[str, tuple[str, ...]] = {
    "pay_details": ("effective_from",),
    "employment_history": ("start_date", "end_date"),
    "timesheets": ("start_datetime", "end_datetime", "pay_period_start", "pay_period_end"),
    "rostered_shifts": ("rostered_start_datetime", "rostered_end_datetime"),
    "payroll_earnings": ("pay_period_start", "pay_period_end", "earning_date"),
    "pay_runs": ("pay_period_start", "pay_period_end"),
    "industrial_instrument_history": ("effective_from", "effective_to"),
    "part_time_patterns": ("effective_from", "effective_to"),
    "part_time_variations": ("shift_date",),
    "public_holiday_overrides": ("holiday_date",),
    "overtime_rest_controls": ("shift_start",),
    "meal_break_events": ("scheduled_break_start", "actual_break_start"),
    "supplemental_events": ("start_datetime", "end_datetime"),
    "toil_register": (
        "overtime_datetime",
        "agreement_date",
        "time_off_date",
        "payment_requested_date",
        "payment_date",
    ),
}

NUMERIC_FIELDS: dict[str, tuple[str, ...]] = {
    "timesheets": ("unpaid_break_minutes", "sleepover_active_minutes"),
    "rostered_shifts": ("rostered_break_minutes",),
    "payroll_earnings": ("hours", "rate", "amount"),
    "part_time_patterns": ("guaranteed_hours",),
    "meal_break_events": ("deducted_break_minutes", "paid_meal_minutes"),
    "supplemental_events": ("hours",),
    "toil_register": ("overtime_hours", "time_off_hours"),
}

_DAY_FIRST_RE = re.compile(r"^\s*\d{1,2}[-/]\d{1,2}[-/]\d{4}(?:\s|T|$)")
_YEAR_FIRST_RE = re.compile(r"^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s|T|$)")


def parse_datetime_value(value: Any):
    """Parse canonical dates without confusing Australian and ISO date order.

    Day-first parsing is applied only when the value actually starts with a
    DD-MM-YYYY or DD/MM/YYYY shape. ISO YYYY-MM-DD values remain year-first.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return pd.NaT
    if _DAY_FIRST_RE.match(text):
        return pd.to_datetime(text, errors="coerce", dayfirst=True)
    if _YEAR_FIRST_RE.match(text):
        return pd.to_datetime(text, errors="coerce", yearfirst=True)
    return pd.to_datetime(text, errors="coerce")


def parse_datetime_series(series: pd.Series) -> pd.Series:
    return series.map(parse_datetime_value)


def _nonblank(series: pd.Series) -> pd.Series:
    return ~(series.isna() | series.astype(str).str.strip().str.lower().isin({"", "nan", "nat", "none"}))


def normalize_canonical_frame(dataset: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce one canonical dataset and retain flags for invalid numeric evidence."""
    if frame is None or frame.empty:
        return frame.copy() if frame is not None else pd.DataFrame()
    out = frame.copy()

    for field in DATE_FIELDS.get(dataset, ()):
        if field in out.columns:
            out[field] = parse_datetime_series(out[field])

    for field in NUMERIC_FIELDS.get(dataset, ()):
        if field not in out.columns:
            continue
        original = out[field].copy()
        converted = pd.to_numeric(original, errors="coerce")
        invalid = _nonblank(original) & converted.isna()
        if bool(invalid.any()):
            out[f"_invalid_{field}"] = invalid
        out[field] = converted

    return out


def normalize_canonical_frames(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Normalize all canonical file datasets before readiness or calculation."""
    return {
        name: normalize_canonical_frame(name, frame)
        for name, frame in frames.items()
    }
