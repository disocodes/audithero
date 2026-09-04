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
    "date": ["date", "shift date", "work date", "timesheet date", "earning date"],
    "effective_from": ["effective from", "effective date", "rate effective date", "pay rate effective date", "rate start date", "commencement date"],
    "effective_to": ["effective to", "end date", "rate end date", "expiry date"],
    "start": ["start datetime", "shift start", "clock in", "start time", "start"],
    "end": ["end datetime", "shift end", "clock out", "finish time", "end time", "finish", "end"],
    "hours": ["worked hours", "hours worked", "total hours", "ordinary hours", "hours", "units", "quantity"],
    "break_minutes": ["unpaid break minutes", "break minutes", "meal break minutes"],
    "hourly_rate": ["hourly rate", "base hourly rate", "base rate", "pay rate", "rate per hour", "unit rate", "rate"],
    "actual_amount": ["paid amount", "actual amount", "gross amount", "line amount", "earnings amount", "shift amount", "amount", "gross", "value"],
    "pay_category": ["pay category", "earnings category", "earning category", "earning name", "earning type", "earnings type", "pay item", "pay code", "pay element"],
    "employment_type": ["employment type", "employment status", "contract type", "engagement type"],
    "classification": ["classification", "award classification", "schads classification", "pay level", "award level", "level"],
    "state": ["work state", "location state", "state"],
    "work_group": ["work group", "award stream", "service type", "sector"],
    "work_type": ["work type", "shift type", "activity", "position", "role", "job title"],
    "pay_period_start": ["pay period start", "period start", "payrun start", "pay run start"],
    "pay_period_end": ["pay period end", "period end", "payrun end", "pay run end"],
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


def _row_id(prefix: str, *parts: Any) -> str:
    text = "|".join(str(x or "").strip() for x in parts)
    return f"AUTO-{prefix}-" + sha1(text.encode()).hexdigest()[:18].upper()


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
    """Infer a work group only from source text that explicitly names the stream."""
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
    payroll_required = (
        mapped["employee_id"], mapped["pay_period_start"], mapped["pay_period_end"],
        mapped["pay_category"], mapped["actual_amount"],
    )
    return {
        "file": file,
        "sheet": sheet,
        "frame": frame,
        "mapped": mapped,
        "timesheet": bool(identity and mapped["start"] and mapped["end"]),
        "payroll": bool(all(payroll_required)),
        "attributes": bool(identity and any(mapped[x] for x in ("hourly_rate", "employment_type", "classification", "state", "work_group", "work_type"))),
    }


def _row_effective_date(row, mapped, *, shift_start=None):
    if mapped.get("effective_from") and not _blank(row.get(mapped["effective_from"])):
        return parse_datetime_value(row.get(mapped["effective_from"]))
    if mapped.get("date") and not _blank(row.get(mapped["date"])):
        return parse_datetime_value(row.get(mapped["date"]))
    if shift_start is not None and not pd.isna(shift_start):
        return pd.Timestamp(shift_start).normalize()
    return pd.NaT


def _first_nonblank(series):
    for value in series:
        if not _blank(value):
            return value
    return None


def _interpretation_rows(descriptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for desc in descriptions:
        roles = []
        if desc.get("timesheet"):
            roles.append("timesheets")
        if desc.get("payroll"):
            roles.append("payroll_earnings")
        if desc.get("attributes"):
            roles.append("employee_or_rate_attributes")
        rows.append({
            "source_file": desc["file"],
            "source_sheet": desc["sheet"],
            "detected_roles": roles or ["unclassified"],
            "mapped_fields": {k: v for k, v in desc["mapped"].items() if v},
            "sample_rows": len(desc["frame"]),
        })
    return rows


def build_auto_canonical(source_root: str | Path) -> dict[str, Any]:
    """Infer canonical inputs from ordinary CSV/XLSX files.

    Automatic intake is intentionally conservative. It maps only recognisable
    structural fields and does not invent work groups, employment types,
    industrial instruments or classifications. Missing facts remain blank and are
    surfaced by the entitlement/readiness layers as review requirements.

    A timesheet needs employee name/ID plus shift start/end. A standalone payroll
    earning source is recognised only when employee ID, pay-period start/end,
    pay category and amount are all present. Pay-category treatment is never
    guessed; reconciliation remains unavailable until a controlled mapping exists.
    """
    root = Path(source_root)
    if not root.exists():
        raise FileNotFoundError(f"Source folder does not exist: {root}")
    descriptions = [_describe(*item) for item in _source_items(root)]
    if not descriptions:
        raise ValueError("No CSV/XLSX source files were found.")

    timesheet_rows: list[dict[str, Any]] = []
    attribute_rows: list[dict[str, Any]] = []
    payroll_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for desc in descriptions:
        df, m = desc["frame"], desc["mapped"]
        label = desc["file"] if desc["sheet"] is None else f"{desc['file']}#{desc['sheet']}"
        row_shift_starts: dict[Any, Any] = {}

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
                row_shift_starts[row_no] = start
                elapsed = (end - start).total_seconds() / 3600
                hours = pd.to_numeric(pd.Series([row.get(m["hours"]) if m["hours"] else None]), errors="coerce").iloc[0]
                break_minutes = pd.to_numeric(pd.Series([row.get(m["break_minutes"]) if m["break_minutes"] else None]), errors="coerce").iloc[0]
                if pd.isna(break_minutes) and not pd.isna(hours):
                    inferred = (elapsed - float(hours)) * 60
                    break_minutes = max(0.0, inferred) if -1 <= inferred <= 480 else float("nan")
                work_type = row.get(m["work_type"]) if m["work_type"] else None
                work_group = row.get(m["work_group"]) if m["work_group"] else None
                supplied_rate = pd.to_numeric(pd.Series([row.get(m["hourly_rate"]) if m["hourly_rate"] else None]), errors="coerce").iloc[0]
                actual_amount = pd.to_numeric(pd.Series([row.get(m["actual_amount"]) if m["actual_amount"] else None]), errors="coerce").iloc[0]
                timesheet_rows.append({
                    "timesheet_id": _row_id("TS", label, row_no, eid, start, end),
                    "employee_id": eid,
                    "employee_name_source": None if _blank(name) else str(name).strip(),
                    "start_datetime": start,
                    "end_datetime": end,
                    "units": None if pd.isna(hours) else float(hours),
                    "unpaid_break_minutes": None if pd.isna(break_minutes) else round(float(break_minutes), 2),
                    "work_group": _work_group(work_group) or _work_group(work_type),
                    "location_state": None if not m["state"] or _blank(row.get(m["state"])) else str(row.get(m["state"])).strip().upper(),
                    "work_type_name": None if _blank(work_type) else str(work_type).strip(),
                    "is_sleepover": "sleepover" in _norm(work_type),
                    "pay_period_start": parse_datetime_value(row.get(m["pay_period_start"])) if m["pay_period_start"] and not _blank(row.get(m["pay_period_start"])) else pd.NaT,
                    "pay_period_end": parse_datetime_value(row.get(m["pay_period_end"])) if m["pay_period_end"] and not _blank(row.get(m["pay_period_end"])) else pd.NaT,
                    "source_supplied_base_hourly_rate": None if pd.isna(supplied_rate) else float(supplied_rate),
                    "source_actual_amount": None if pd.isna(actual_amount) else float(actual_amount),
                    "source_file": desc["file"],
                    "source_sheet": desc["sheet"],
                    "source_row": int(row_no) + 2,
                })

        if desc["payroll"]:
            for row_no, row in df.iterrows():
                source_id = row.get(m["employee_id"])
                if _blank(source_id):
                    continue
                period_start = parse_datetime_value(row.get(m["pay_period_start"]))
                period_end = parse_datetime_value(row.get(m["pay_period_end"]))
                pay_category = row.get(m["pay_category"])
                amount = pd.to_numeric(pd.Series([row.get(m["actual_amount"])]), errors="coerce").iloc[0]
                if pd.isna(period_start) or pd.isna(period_end) or _blank(pay_category) or pd.isna(amount):
                    continue
                hours = pd.to_numeric(pd.Series([row.get(m["hours"]) if m["hours"] else None]), errors="coerce").iloc[0]
                rate = pd.to_numeric(pd.Series([row.get(m["hourly_rate"]) if m["hourly_rate"] else None]), errors="coerce").iloc[0]
                earning_date = parse_datetime_value(row.get(m["date"])) if m["date"] and not _blank(row.get(m["date"])) else pd.NaT
                payroll_rows.append({
                    "payroll_line_id": _row_id("PAY", label, row_no, source_id, period_start, period_end, pay_category, amount),
                    "employee_id": str(source_id).strip(),
                    "pay_period_start": period_start,
                    "pay_period_end": period_end,
                    "pay_category": str(pay_category).strip(),
                    "earning_date": earning_date,
                    "hours": None if pd.isna(hours) else float(hours),
                    "rate": None if pd.isna(rate) else float(rate),
                    "amount": float(amount),
                    "source_file": desc["file"],
                    "source_sheet": desc["sheet"],
                    "source_row": int(row_no) + 2,
                })

        if desc["attributes"] or desc["timesheet"]:
            for row_no, row in df.iterrows():
                name = row.get(m["employee_name"]) if m["employee_name"] else None
                source_id = row.get(m["employee_id"]) if m["employee_id"] else None
                if _blank(name) and _blank(source_id):
                    continue
                classification = row.get(m["classification"]) if m["classification"] else None
                work_type = row.get(m["work_type"]) if m["work_type"] else None
                group_value = row.get(m["work_group"]) if m["work_group"] else None
                rate = pd.to_numeric(pd.Series([row.get(m["hourly_rate"]) if m["hourly_rate"] else None]), errors="coerce").iloc[0]
                effective_from = _row_effective_date(row, m, shift_start=row_shift_starts.get(row_no))
                effective_to = parse_datetime_value(row.get(m["effective_to"])) if m["effective_to"] and not _blank(row.get(m["effective_to"])) else pd.NaT
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
                    "effective_from": effective_from,
                    "effective_to": effective_to,
                    "source_item": label,
                    "source_row": int(row_no) + 2,
                })

    timesheets = pd.DataFrame(timesheet_rows)
    if timesheets.empty:
        raise ValueError("Could not identify a usable timesheet. Supply employee name/ID plus shift start and end columns.")
    attributes = pd.DataFrame(attribute_rows)
    names = timesheets[["employee_id", "employee_name_source"]].drop_duplicates().rename(columns={"employee_name_source": "employee_name"})
    attributes = names.copy() if attributes.empty else pd.concat([attributes, names], ignore_index=True, sort=False)

    employees, histories, pay_details = [], [], []
    first_shift = timesheets.groupby("employee_id")["start_datetime"].min().to_dict()
    for raw_eid, group in attributes.groupby("employee_id", dropna=False):
        eid = str(raw_eid)
        name = _first_nonblank(group.get("employee_name", pd.Series(dtype=object))) or eid
        state = _first_nonblank(group.get("state", pd.Series(dtype=object)))
        work_group = _first_nonblank(group.get("work_group", pd.Series(dtype=object)))
        dated = group.copy()
        dated["_effective"] = pd.to_datetime(dated.get("effective_from"), errors="coerce")
        dated = dated.sort_values("_effective", na_position="last")
        current_emp_type = _first_nonblank(dated.get("employment_type", pd.Series(dtype=object)))
        nonblank_types = dated[dated.get("employment_type", pd.Series(index=dated.index, dtype=object)).notna()]
        if not nonblank_types.empty:
            current_emp_type = nonblank_types.iloc[-1].get("employment_type")
        employees.append({"employee_id": eid, "employee_name": str(name), "employment_type_current": current_emp_type, "state": state, "work_group": work_group, "auto_intake": True})

        history_candidates = dated[dated.get("employment_type", pd.Series(index=dated.index, dtype=object)).notna()].copy()
        if history_candidates.empty:
            histories.append({"employee_id": eid, "start_date": first_shift.get(raw_eid) or first_shift.get(eid), "end_date": pd.NaT, "employment_type": None, "contract_type": None, "title": _first_nonblank(group.get("work_type_name", pd.Series(dtype=object))), "auto_intake": True})
        else:
            for _, candidate in history_candidates.drop_duplicates(subset=["_effective", "employment_type"]).iterrows():
                eff = candidate.get("_effective")
                if pd.isna(eff):
                    eff = first_shift.get(raw_eid) or first_shift.get(eid)
                histories.append({"employee_id": eid, "start_date": eff, "end_date": candidate.get("effective_to"), "employment_type": candidate.get("employment_type"), "contract_type": None, "title": candidate.get("work_type_name"), "auto_intake": True})

        pay_candidates = dated[(dated.get("classification_code", pd.Series(index=dated.index, dtype=object)).notna()) | (dated.get("classification_name", pd.Series(index=dated.index, dtype=object)).notna()) | (dated.get("supplied_hourly_rate", pd.Series(index=dated.index, dtype=float)).notna())].copy()
        if pay_candidates.empty:
            pay_candidates = dated.iloc[:1]
        rate_series = pd.to_numeric(pay_candidates.get("supplied_hourly_rate", pd.Series(index=pay_candidates.index, dtype=float)), errors="coerce")
        undated_rates = pay_candidates[rate_series.notna() & pay_candidates["_effective"].isna()]
        distinct_undated = pd.to_numeric(undated_rates.get("supplied_hourly_rate"), errors="coerce").dropna().unique()
        if len(distinct_undated) > 1:
            warnings.append(f"{name}: multiple different hourly rates were supplied without effective dates; rate chronology requires review.")
        for _, candidate in pay_candidates.drop_duplicates(subset=["_effective", "classification_code", "classification_name", "supplied_hourly_rate"]).iterrows():
            eff = candidate.get("_effective")
            if pd.isna(eff):
                eff = first_shift.get(raw_eid) or first_shift.get(eid)
            pay_details.append({
                "employee_id": eid,
                "effective_from": eff,
                "classification_code": candidate.get("classification_code"),
                "classification_name": candidate.get("classification_name"),
                "industrial_instrument": None,
                "supplied_hourly_rate": candidate.get("supplied_hourly_rate"),
                "source_reference": candidate.get("source_item"),
                "source_row": candidate.get("source_row"),
                "auto_intake": True,
            })

    employee_df = pd.DataFrame(employees)
    lookup = employee_df.set_index("employee_id").to_dict("index")
    for idx, row in timesheets.iterrows():
        emp = lookup.get(str(row["employee_id"]), {})
        if _blank(row.get("location_state")):
            timesheets.at[idx, "location_state"] = emp.get("state")
        if _blank(row.get("work_group")):
            timesheets.at[idx, "work_group"] = emp.get("work_group")

    payroll_df = pd.DataFrame(payroll_rows)
    pay_runs = pd.DataFrame()
    if not payroll_df.empty:
        pay_runs = payroll_df[["pay_period_start", "pay_period_end"]].dropna().drop_duplicates().copy()
        pay_runs["pay_run_id"] = [f"AUTO-PP-{i+1}" for i in range(len(pay_runs))]
    elif timesheets["pay_period_start"].notna().any():
        pay_runs = timesheets[["pay_period_start", "pay_period_end"]].dropna().drop_duplicates().copy()
        pay_runs["pay_run_id"] = [f"AUTO-PP-{i+1}" for i in range(len(pay_runs))]

    if not payroll_df.empty:
        warnings.append("Payroll earning lines were detected. Actual-pay reconciliation remains disabled until pay categories have an approved treatment mapping.")
    if employee_df.get("work_group", pd.Series(dtype=object)).isna().any():
        warnings.append("One or more employee work groups could not be established from source evidence and will require review for Award-condition analysis.")
    if pd.DataFrame(histories).get("employment_type", pd.Series(dtype=object)).isna().any():
        warnings.append("One or more employment types could not be established from source evidence and will require review.")

    starts = pd.to_datetime(timesheets["start_datetime"], errors="coerce").dropna()
    frames = {
        "employees": employee_df,
        "pay_details": pd.DataFrame(pay_details),
        "employment_history": pd.DataFrame(histories),
        "timesheets": timesheets.drop(columns=["employee_name_source"], errors="ignore"),
        "pay_runs": pay_runs,
    }
    if not payroll_df.empty:
        frames["payroll_earnings"] = payroll_df

    return {
        "frames": frames,
        "metadata": {
            "source_items": [d["file"] if d["sheet"] is None else f"{d['file']}#{d['sheet']}" for d in descriptions],
            "timesheet_items": [d["file"] if d["sheet"] is None else f"{d['file']}#{d['sheet']}" for d in descriptions if d["timesheet"]],
            "payroll_items": [d["file"] if d["sheet"] is None else f"{d['file']}#{d['sheet']}" for d in descriptions if d["payroll"]],
            "interpretation": _interpretation_rows(descriptions),
            "employees": len(employee_df),
            "timesheets": len(timesheets),
            "payroll_earning_rows": len(payroll_df),
            "rate_history_rows": len(pay_details),
            "warnings": warnings,
            "start_date": None if starts.empty else str(starts.min().date()),
            "end_date": None if starts.empty else str(starts.max().date()),
        },
    }
