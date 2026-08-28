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


def load_file_source(input_root: str | Path, start_date=None, end_date=None) -> dict[str, pd.DataFrame]:
    """Load canonical AuditHero input files from CSV or Excel.

    Expected stems: employees, pay_details, employment_history, timesheets,
    rostered_shifts, payroll_earnings, pay_runs. The first five are sufficient
    for entitlement-only auditing; payroll_earnings/pay_runs enable actual-vs-
    expected reconciliation.
    """
    root = Path(input_root)
    if not root.exists():
        raise FileNotFoundError(f"AuditHero input folder does not exist: {root}")
    frames = {}
    for key, stem in CANONICAL_INPUTS.items():
        p = _resolve(root, stem)
        frames[key] = _read_table(p) if p else pd.DataFrame()

    required = ["employees", "pay_details", "employment_history", "timesheets"]
    missing = [k for k in required if frames[k].empty]
    if missing:
        raise ValueError(
            "Missing required manual input(s): " + ", ".join(missing) +
            f". Upload CSV/XLSX files to {root}."
        )

    if start_date or end_date:
        ts = frames["timesheets"].copy()
        if "start_datetime" in ts.columns:
            d = pd.to_datetime(ts["start_datetime"], errors="coerce")
            if start_date:
                ts = ts[d >= pd.to_datetime(start_date)]
                d = pd.to_datetime(ts["start_datetime"], errors="coerce")
            if end_date:
                ts = ts[d < pd.to_datetime(end_date) + pd.Timedelta(days=1)]
            frames["timesheets"] = ts
    return frames


def input_inventory(input_root: str | Path) -> pd.DataFrame:
    root=Path(input_root)
    rows=[]
    for key,stem in CANONICAL_INPUTS.items():
        p=_resolve(root,stem) if root.exists() else None
        rows.append({
            "dataset": key,
            "required": key in {"employees","pay_details","employment_history","timesheets"},
            "found": bool(p),
            "file": str(p) if p else None,
        })
    return pd.DataFrame(rows)
