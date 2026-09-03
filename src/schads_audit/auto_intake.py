from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import re
from typing import Any

import pandas as pd

from .canonical_normalization import parse_datetime_value
from .normalize import infer_schads_classification


ALIASES = {
    "employee_id": ["employee id", "employee number", "employee no", "staff id", "worker id", "emp id"],
    "employee_name": ["employee name", "full name", "staff name", "worker name", "employee", "name"],
    "date": ["date", "shift date", "work date", "timesheet date"],
    "start": ["start datetime", "shift start", "clock in", "start time", "start"],
    "end": ["end datetime", "shift end", "clock out", "finish time", "end time", "finish", "end"],
    "hours": ["worked hours", "hours worked", "total hours", "ordinary hours", "hours", "units"],
    "break_minutes": ["unpaid break minutes", "break minutes", "meal break minutes"],
    "hourly_rate": ["hourly rate", "base hourly rate", "base rate", "pay rate", "rate per hour", "rate"],
    "actual_amount": ["paid amount", "actual amount", "gross amount", "line amount", "earnings amount"],
    "employment_type": ["employment type", "employment status", "contract type", "engagement type"],
    "classification": ["classification", "award classification", "schads classification", "pay level", "award level", "level"],
    "state": ["work state", "location state", "state"],
    "work_group": ["work group", "award stream", "service type", "sector"],
    "work_type": ["work type", "shift type", "activity", "position", "role", "job title"],
    "pay_period_start": ["pay period start", "period start", "payrun start"],
    "pay_period_end": ["pay period end", "period end", "payrun end"],
}


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _score(column: str, alias: str) -> float:
    c, a = _norm(column), _norm(alias)
    if not c or not a:
        return 0.0
    if c == a:
        return 1.0
    ct, at = set(c.split()), set(a.split())
    if at and at.issubset(ct):
        return 0.95
    if ct and ct.issubset(at) and len(ct) > 1:
        return 0.88
    return 0.0


def _column(columns: list[str], field: str, minimum: float = 0.88) -> str | None:
    best, best_score = None, 0.0
    for column in columns:
        score = max(_score(column, alias) for alias in ALIASES[field])
        if score > best_score:
            best, best_score = column, score
    return best if best_score >= minimum else None


def _blank(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    return str(value).strip().lower() in {"", "nan", "nat", "none"}


def _employee_id(value: Any, name: Any) -> str:
    if not _blank(value):
        return str(value).strip()
    text = _norm(name)
    return "AUTO-" + sha1(text.encode()).hexdigest()[:16].upper()


def _row_id(*parts: Any) -> str:
    text = "|".join(str(x or "").strip() for x in parts)
    return "AUTO-TS-" + sha1(text.encode()).hexdigest()[:18].upper()


def _emp_type(value: Any) -> str | None:
    text = _norm(value)
    if "casual" in text:
        return "CASUAL"
    if "part" in text and "time" in text:
        return "PART_TIME"
    if "full" in text and "time" in text:
        return "FULL_TIME"
    return None


def _work_group(value: Any) -> str | None:
    text = _norm(value)
    if not text:
        return None
    if "home care" in text:
        return "HOME_CARE"
    if "disability" in text or "support worker" in text or "support work" in text:
        return "DISABILITY_SERVICES"
    if "social" in text or "community" in text:
        return "SACS_NON_DISABILITY"
    return None


def _datetime(date_value: Any, time_value: Any):
    if _blank(time_value):
        return pd.NaT
    raw = str(time_value).strip()
    # Full timestamp supplied in the time column.
    if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}", raw):
        return parse_datetime_value(raw)
    if not _blank(date_value):
        return parse_datetime_value(f"{str(date_value).strip()} {raw}")
    return parse_datetime_value(raw)


def _source_items(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        if path.suffix.lower() == ".csv":
            yield rel, None, pd.read_csv(path)
        elif path.suffix.lower() in {".xlsx", ".xlsm"}:
            book = pd.ExcelFile(path)
            for sheet in book.sheet_names:
                yield rel, sheet, pd.read_excel(path, sheet_name=sheet)


def _describe(file: str, sheet: str | None, frame: pd.DataFrame):
    columns = list(frame.columns)
    mapped = {field: _column(columns, field) for field in ALIASES}
    identity = bool(mapped["employee_id"] or mapped["employee_name"])
    return {
        "file": file,
        "sheet": sheet,
        "frame": frame,
        "mapped": mapped,
        "timesheet": bool(identity and mapped["start"] and mapped["end"]),
        "attributes": bool(identity and any(mapped[x] for x in ("hourly_rate", "employment_type", "classification", "state", "work_group", "work_type"))),
    }


def build_auto_canonical(source_root: str | Path) -> dict[str, Any]:
    """Infer canonical AuditHero inputs from ordinary CSV/XLSX files.

    A usable timesheet needs only an employee name/ID and shift start/end. Optional
    files or columns enrich employment type, SCHADS classification, state, work
    stream and supplied hourly rate. Missing optional facts are preserved as
    unknowns for the Award scenario engine rather than blocking the audit.
    """
    root = Path(source_root)
    if not root.exists():
        raise FileNotFoundError(f"Source folder does not exist: {root}")
    descriptions = [_describe(*item) for item in _source_items(root)]
    if not descriptions:
        raise ValueError("No CSV/XLSX source files were found.")

    timesheet_rows: list[dict[str, Any]] = []
    attribute_rows: list[dict[str, Any]] = []

    for desc in descriptions:
        df, m = desc["frame"], desc["mapped"]
        label = desc["file"] if desc["sheet"] is None else f"{desc['file']}#{desc['sheet']}"
        if desc["timesheet"]:
            for row_no, row in df.iterrows():
                name = row.get(m["employee_name"]) if m["employee_name"] else None
                source_id = row.get(m["employee_id"]) if m["employee_id"] else None
                eid = _employee_id(source_id, name)
                date_value = row.get(m["date"]) if m["date"] else None
                start = _datetime(date_value, row.get(m["start"]))
                end = _datetime(date_value, row.get(m["end"]))
                if pd.isna(start) or pd.isna(end):
                    continue
                if end <= start and not _blank(date_value):
                    end += pd.Timedelta(days=1)
                if end <= start:
                    continue
                elapsed = (end - start).total_seconds() / 3600
                hours = pd.to_numeric(pd.Series([row.get(m["hours"]) if m["hours"] else None]), errors="coerce").iloc[0]
                break_minutes = pd.to_numeric(pd.Series([row.get(m["break_minutes"]) if m["break_minutes"] else None]), errors="coerce").iloc[0]
                if pd.isna(break_minutes) and not pd.isna(hours):
                    inferred = (elapsed - float(hours)) * 60
                    break_minutes = max(0.0, inferred) if -1 <= inferred <= 480 else float("nan")
                work_type = row.get(m["work_type"]) if m["work_type"] else None
                work_group = row.get(m["work_group"]) if m["work_group"] else None
                actual_rate = pd.to_numeric(pd.Series([row.get(m["hourly_rate"]) if m["hourly_rate"] else None]), errors="coerce").iloc[0]
                actual_amount = pd.to_numeric(pd.Series([row.get(m["actual_amount"]) if m["actual_amount"] else None]), errors="coerce").iloc[0]
                timesheet_rows.append({
                    "timesheet_id": _row_id(label, row_no, eid, start, end),
                    "employee_id": eid,
                    "employee_name_source": None if _blank(name) else str(name).strip(),
                    "start_datetime": start,
                    "end_datetime": end,
                    "units": None if pd.isna(hours) else float(hours),
                    "unpaid_break_minutes": None if pd.isna(break_minutes) else round(float(break_minutes), 2),
                    "work_group": _work_group(work_group) or _work_group(work_type) or "DISABILITY_SERVICES",
                    "location_state": None if not m["state"] or _blank(row.get(m["state"])) else str(row.get(m["state"])).strip().upper(),
                    "work_type_name": None if _blank(work_type) else str(work_type).strip(),
                    "is_sleepover": "sleepover" in _norm(work_type),
                    "pay_period_start": parse_datetime_value(row.get(m["pay_period_start"])) if m["pay_period_start"] and not _blank(row.get(m["pay_period_start"])) else pd.NaT,
                    "pay_period_end": parse_datetime_value(row.get(m["pay_period_end"])) if m["pay_period_end"] and not _blank(row.get(m["pay_period_end"])) else pd.NaT,
                    "source_actual_hourly_rate": None if pd.isna(actual_rate) else float(actual_rate),
                    "source_actual_amount": None if pd.isna(actual_amount) else float(actual_amount),
                    "source_file": desc["file"],
                    "source_sheet": desc["sheet"],
                    "source_row": int(row_no) + 2,
                })

        if desc["attributes"] or desc["timesheet"]:
            for _, row in df.iterrows():
                name = row.get(m["employee_name"]) if m["employee_name"] else None
                source_id = row.get(m["employee_id"]) if m["employee_id"] else None
                if _blank(name) and _blank(source_id):
                    continue
                classification = row.get(m["classification"]) if m["classification"] else None
                work_type = row.get(m["work_type"]) if m["work_type"] else None
                group_value = row.get(m["work_group"]) if m["work_group"] else None
                rate = pd.to_numeric(pd.Series([row.get(m["hourly_rate"]) if m["hourly_rate"] else None]), errors="coerce").iloc[0]
                attribute_rows.append({
                    "employee_id": _employee_id(source_id, name),
                    "employee_name": None if _blank(name) else str(name).strip(),
                    "employment_type": _emp_type(row.get(m["employment_type"])) if m["employment_type"] else None,
                    "classification_name": None if _blank(classification) else str(classification).strip(),
                    "classification_code": infer_schads_classification(classification),
                    "state": None if not m["state"] or _blank(row.get(m["state"])) else str(row.get(m["state"])).strip().upper(),
                    "work_group": _work_group(group_value) or _work_group(work_type),
                    "work_type_name": None if _blank(work_type) else str(work_type).strip(),
                    "supplied_hourly_rate": None if pd.isna(rate) else float(rate),
                    "source_item": label,
                })

    timesheets = pd.DataFrame(timesheet_rows)
    if timesheets.empty:
        raise ValueError("Could not identify a usable timesheet. Supply employee name/ID plus shift start and end columns.")
    attributes = pd.DataFrame(attribute_rows)

    names = timesheets[["employee_id", "employee_name_source"]].drop_duplicates().rename(columns={"employee_name_source": "employee_name"})
    if attributes.empty:
        attributes = names.copy()
    else:
        attributes = pd.concat([attributes, names], ignore_index=True, sort=False)

    def first_nonblank(series):
        for value in series:
            if not _blank(value):
                return value
        return None

    employees, histories, pay_details = [], [], []
    first_shift = timesheets.groupby("employee_id")["start_datetime"].min().to_dict()
    for eid, group in attributes.groupby("employee_id", dropna=False):
        eid = str(eid)
        name = first_nonblank(group.get("employee_name", pd.Series(dtype=object))) or eid
        emp_type = first_nonblank(group.get("employment_type", pd.Series(dtype=object)))
        state = first_nonblank(group.get("state", pd.Series(dtype=object)))
        work_group = first_nonblank(group.get("work_group", pd.Series(dtype=object))) or "DISABILITY_SERVICES"
        employees.append({"employee_id": eid, "employee_name": str(name), "employment_type_current": emp_type, "state": state, "work_group": work_group, "auto_intake": True})
        histories.append({"employee_id": eid, "start_date": first_shift.get(eid), "end_date": pd.NaT, "employment_type": emp_type or "UNKNOWN", "contract_type": None, "title": first_nonblank(group.get("work_type_name", pd.Series(dtype=object))), "auto_intake": True})
        candidates = group[(group.get("classification_code", pd.Series(index=group.index, dtype=object)).notna()) | (group.get("classification_name", pd.Series(index=group.index, dtype=object)).notna()) | (group.get("supplied_hourly_rate", pd.Series(index=group.index, dtype=float)).notna())]
        if candidates.empty:
            candidates = group.iloc[:1]
        for _, candidate in candidates.iterrows():
            pay_details.append({
                "employee_id": eid,
                "effective_from": first_shift.get(eid),
                "classification_code": candidate.get("classification_code"),
                "classification_name": candidate.get("classification_name"),
                "industrial_instrument": "SCHADS",
                "supplied_hourly_rate": candidate.get("supplied_hourly_rate"),
                "auto_intake": True,
            })

    employee_df = pd.DataFrame(employees)
    lookup = employee_df.set_index("employee_id").to_dict("index")
    for idx, row in timesheets.iterrows():
        emp = lookup.get(str(row["employee_id"]), {})
        if _blank(row.get("location_state")):
            timesheets.at[idx, "location_state"] = emp.get("state")
        if _blank(row.get("work_group")):
            timesheets.at[idx, "work_group"] = emp.get("work_group") or "DISABILITY_SERVICES"

    pay_runs = pd.DataFrame()
    if timesheets["pay_period_start"].notna().any():
        pay_runs = timesheets[["pay_period_start", "pay_period_end"]].dropna().drop_duplicates().copy()
        pay_runs["pay_run_id"] = [f"AUTO-PP-{i+1}" for i in range(len(pay_runs))]

    starts = pd.to_datetime(timesheets["start_datetime"], errors="coerce").dropna()
    return {
        "frames": {
            "employees": employee_df,
            "pay_details": pd.DataFrame(pay_details),
            "employment_history": pd.DataFrame(histories),
            "timesheets": timesheets.drop(columns=["employee_name_source"], errors="ignore"),
            "pay_runs": pay_runs,
        },
        "metadata": {
            "source_items": [d["file"] if d["sheet"] is None else f"{d['file']}#{d['sheet']}" for d in descriptions],
            "timesheet_items": [d["file"] if d["sheet"] is None else f"{d['file']}#{d['sheet']}" for d in descriptions if d["timesheet"]],
            "employees": len(employee_df),
            "timesheets": len(timesheets),
            "start_date": None if starts.empty else str(starts.min().date()),
            "end_date": None if starts.empty else str(starts.max().date()),
        },
    }
