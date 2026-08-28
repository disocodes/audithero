from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def read_register(path: str | Path) -> pd.DataFrame:
    """Read a controlled CSV register, returning an empty frame for missing/header-only files."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def normalize_employee_ids(values: Iterable[object]) -> set[str]:
    return {
        str(v).strip()
        for v in values
        if v is not None and str(v).strip() and str(v).strip().lower() != "nan"
    }


def employee_register_coverage(
    register: pd.DataFrame,
    required_employee_ids: Iterable[object],
    *,
    employee_column: str = "employee_id",
) -> dict[str, object]:
    """Return employee-level coverage for a controlled historical register.

    This intentionally does not claim effective-date continuity. Detailed audit modules
    still test whether the applicable effective-dated record covers each shift/event.
    The readiness gate only establishes that each relevant employee has controlled
    evidence loaded at all, preventing sample/example rows from satisfying the gate.
    """
    required = normalize_employee_ids(required_employee_ids)
    if not required:
        return {
            "required": set(),
            "present": set(),
            "missing": set(),
            "covered": True,
        }

    if register is None or register.empty or employee_column not in register.columns:
        present: set[str] = set()
    else:
        present = normalize_employee_ids(register[employee_column].tolist())

    missing = required - present
    return {
        "required": required,
        "present": present,
        "missing": missing,
        "covered": not missing,
    }


def coverage_detail(result: dict[str, object], label: str) -> str:
    required = sorted(result.get("required") or [])
    missing = sorted(result.get("missing") or [])
    if not required:
        return f"No employees require {label}."
    if missing:
        preview = ", ".join(missing[:10])
        suffix = f" (+{len(missing)-10} more)" if len(missing) > 10 else ""
        return (
            f"{len(missing)} of {len(required)} required employees have no {label} row: "
            f"{preview}{suffix}"
        )
    return f"Controlled {label} rows exist for all {len(required)} required employees."
