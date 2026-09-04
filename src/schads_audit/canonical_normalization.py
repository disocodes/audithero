from __future__ import annotations

from typing import Any

import pandas as pd

from .dates import parse_datetime_series, parse_datetime_value


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
    "supplemental_events": ("start_datetime", "end_datetime", "pay_period_start", "pay_period_end"),
    "toil_register": (
        "overtime_datetime",
        "agreement_date",
        "time_off_date",
        "payment_requested_date",
        "payment_date",
        "employment_end_date",
        "payment_pay_period_start",
        "payment_pay_period_end",
    ),
}

NUMERIC_FIELDS: dict[str, tuple[str, ...]] = {
    "pay_details": ("supplied_hourly_rate",),
    "timesheets": ("unpaid_break_minutes", "sleepover_active_minutes", "units", "source_supplied_base_hourly_rate", "source_actual_amount"),
    "rostered_shifts": ("rostered_break_minutes",),
    "payroll_earnings": ("hours", "rate", "amount"),
    "part_time_patterns": ("guaranteed_hours",),
    "meal_break_events": ("deducted_break_minutes", "paid_meal_minutes"),
    "supplemental_events": ("hours",),
    "toil_register": ("overtime_hours", "time_off_hours"),
}


def numeric_value(value: Any, default: float = 0.0) -> float:
    """Return a finite numeric value or the supplied safe default."""
    if value is None:
        return float(default)
    try:
        converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    except Exception:
        return float(default)
    if pd.isna(converted):
        return float(default)
    return float(converted)


def _nonblank(series: pd.Series) -> pd.Series:
    return ~(series.isna() | series.astype(str).str.strip().str.lower().isin({"", "nan", "nat", "none", "null"}))


def normalize_canonical_frame(dataset: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce one canonical dataset and retain flags for invalid source evidence."""
    if frame is None or frame.empty:
        return frame.copy() if frame is not None else pd.DataFrame()
    out = frame.copy()

    for field in DATE_FIELDS.get(dataset, ()):
        if field not in out.columns:
            continue
        original = out[field].copy()
        converted = parse_datetime_series(original)
        invalid = _nonblank(original) & converted.isna()
        if bool(invalid.any()):
            out[f"_invalid_{field}"] = invalid
        out[field] = converted

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
    return {name: normalize_canonical_frame(name, frame) for name, frame in frames.items()}
