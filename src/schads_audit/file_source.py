from __future__ import annotations
from pathlib import Path
import pandas as pd

CANONICAL_INPUTS = {
    "employees": "employees",
    "pay_details": "pay_details",
    "employment_history": "employment_history",
    "timesheets": "timesheets",
    "rostered_shifts": "rostered_shifts",
    "payroll_earnings": "payroll_earnings",
    "pay_runs": "pay_runs",
}
WORKBOOK_NAMES = ("audithero_input.xlsx", "audithero_input.xlsm")


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported input format: {path.name}")


def _resolve(root: Path, stem: str):
    for ext in (".csv", ".xlsx", ".xlsm", ".xls"):
        p = root / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def _load_workbook(root: Path):
    workbook = next((root / n for n in WORKBOOK_NAMES if (root / n).exists()), None)
    if not workbook:
        return None, {}
    book = pd.ExcelFile(workbook)
    sheet_lookup = {s.lower(): s for s in book.sheet_names}
    frames = {}
    for key, stem in CANONICAL_INPUTS.items():
        sheet = sheet_lookup.get(stem.lower())
        frames[key] = pd.read_excel(workbook, sheet_name=sheet) if sheet else pd.DataFrame()
    return workbook, frames


def load_file_source(input_root: str | Path, start_date=None, end_date=None) -> dict[str, pd.DataFrame]:
    """Load canonical AuditHero inputs without API credentials.

    Two layouts are supported:
      1. One workbook named ``audithero_input.xlsx`` with sheets named after the
         canonical datasets; or
      2. Separate files such as ``employees.csv`` and ``timesheets.xlsx``.

    Required datasets: employees, pay_details, employment_history and timesheets.
    rostered_shifts is recommended for full-time overtime. payroll_earnings/pay_runs
    are optional and enable actual-vs-expected reconciliation.
    """
    root = Path(input_root)
    if not root.exists():
        raise FileNotFoundError(f"AuditHero input folder does not exist: {root}")

    workbook, frames = _load_workbook(root)
    if not workbook:
        frames = {}
        for key, stem in CANONICAL_INPUTS.items():
            p = _resolve(root, stem)
            frames[key] = _read_table(p) if p else pd.DataFrame()

    required = ["employees", "pay_details", "employment_history", "timesheets"]
    missing = [k for k in required if frames[k].empty]
    if missing:
        source = f"workbook {workbook.name}" if workbook else str(root)
        raise ValueError(
            "Missing required manual input dataset(s): " + ", ".join(missing) +
            f". Source checked: {source}."
        )

    if start_date or end_date:
        ts = frames["timesheets"].copy()
        if "start_datetime" not in ts.columns:
            raise ValueError("timesheets input must contain start_datetime")
        d = pd.to_datetime(ts["start_datetime"], errors="coerce")
        if start_date:
            ts = ts[d >= pd.to_datetime(start_date)]
            d = pd.to_datetime(ts["start_datetime"], errors="coerce")
        if end_date:
            ts = ts[d < pd.to_datetime(end_date) + pd.Timedelta(days=1)]
        frames["timesheets"] = ts
    return frames


def input_inventory(input_root: str | Path) -> pd.DataFrame:
    root = Path(input_root)
    workbook, workbook_frames = _load_workbook(root) if root.exists() else (None, {})
    rows = []
    for key, stem in CANONICAL_INPUTS.items():
        if workbook:
            found = not workbook_frames.get(key, pd.DataFrame()).empty
            file = f"{workbook}#{stem}" if found else None
        else:
            p = _resolve(root, stem) if root.exists() else None
            found = bool(p)
            file = str(p) if p else None
        rows.append({
            "dataset": key,
            "required": key in {"employees", "pay_details", "employment_history", "timesheets"},
            "found": found,
            "file": file,
        })
    return pd.DataFrame(rows)
