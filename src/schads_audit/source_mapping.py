from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from .dates import parse_datetime_series
from .canonical_normalization import normalize_canonical_frame


CANONICAL_SCHEMAS: dict[str, dict[str, Any]] = {
    "employees": {
        "required": ["employee_id", "employee_name"],
        "recommended": ["employment_type_current", "state", "work_group"],
        "aliases": {
            "employee_id": ["employee id", "employee number", "employee no", "emp id", "id"],
            "employee_name": ["employee name", "full name", "name", "display name"],
            "employment_type_current": ["employment type", "employment status", "contract type"],
            "state": ["state", "region", "work state"],
            "work_group": ["work group", "service type", "award stream"],
        },
    },
    "pay_details": {
        "required": ["employee_id", "effective_from", "classification_code"],
        "recommended": ["classification_name", "industrial_instrument"],
        "aliases": {
            "employee_id": ["employee id", "employee number", "emp id"],
            "effective_from": ["effective from", "effective date", "start date", "from date"],
            "classification_code": ["classification code", "award classification code", "pay level code"],
            "classification_name": ["classification", "classification name", "pay level", "award level"],
            "industrial_instrument": ["industrial instrument", "award", "agreement", "instrument"],
        },
    },
    "employment_history": {
        "required": ["employee_id", "start_date", "employment_type"],
        "recommended": ["end_date", "contract_type", "title"],
        "aliases": {
            "employee_id": ["employee id", "employee number", "emp id"],
            "start_date": ["start date", "effective from", "employment start"],
            "end_date": ["end date", "effective to", "employment end"],
            "employment_type": ["employment type", "employment status", "contract type"],
            "contract_type": ["contract type", "contract", "engagement type"],
            "title": ["title", "position", "job title", "role"],
        },
    },
    "timesheets": {
        "required": ["timesheet_id", "employee_id", "start_datetime", "end_datetime"],
        "recommended": [
            "unpaid_break_minutes", "work_group", "location_state", "holiday_location_key",
            "work_type_name", "is_sleepover", "sleepover_active_minutes",
            "sleepover_12h_written_agreement", "pay_period_start", "pay_period_end",
        ],
        "aliases": {
            "timesheet_id": ["timesheet id", "entry id", "shift id", "record id"],
            "employee_id": ["employee id", "employee number", "emp id"],
            "start_datetime": ["start datetime", "start time", "clock in", "shift start"],
            "end_datetime": ["end datetime", "end time", "clock out", "shift end"],
            "unpaid_break_minutes": ["unpaid break minutes", "break minutes", "unpaid break"],
            "work_group": ["work group", "service type", "award stream"],
            "location_state": ["location state", "state", "work state"],
            "holiday_location_key": ["holiday location key", "location key", "local holiday key"],
            "work_type_name": ["work type", "work type name", "activity", "shift type"],
            "is_sleepover": ["is sleepover", "sleepover", "sleepover flag"],
            "sleepover_active_minutes": ["sleepover active minutes", "active work minutes"],
            "sleepover_12h_written_agreement": ["sleepover 12h written agreement", "12h agreement"],
            "pay_period_start": ["pay period start", "period start", "payrun start"],
            "pay_period_end": ["pay period end", "period end", "payrun end"],
        },
    },
    "rostered_shifts": {
        "required": ["rostered_shift_id", "employee_id", "rostered_start_datetime", "rostered_end_datetime"],
        "recommended": ["rostered_break_minutes", "work_type_name", "work_site_id"],
        "aliases": {
            "rostered_shift_id": ["rostered shift id", "roster id", "shift id"],
            "employee_id": ["employee id", "employee number", "emp id"],
            "rostered_start_datetime": ["rostered start datetime", "roster start", "scheduled start"],
            "rostered_end_datetime": ["rostered end datetime", "roster end", "scheduled end"],
            "rostered_break_minutes": ["rostered break minutes", "scheduled break minutes"],
            "work_type_name": ["work type", "work type name", "shift type"],
            "work_site_id": ["work site id", "site id", "location id"],
        },
    },
    "payroll_earnings": {
        "required": ["employee_id", "pay_period_start", "pay_period_end", "pay_category", "amount"],
        "recommended": ["payroll_line_id", "pay_run_id", "timesheet_id", "earning_date", "hours", "rate"],
        "aliases": {
            "payroll_line_id": ["payroll line id", "earnings line id", "line id"],
            "pay_run_id": ["pay run id", "payrun id"],
            "employee_id": ["employee id", "employee number", "emp id"],
            "timesheet_id": ["timesheet id", "entry id", "shift id"],
            "pay_period_start": ["pay period start", "period start", "payrun start"],
            "pay_period_end": ["pay period end", "period end", "payrun end"],
            "earning_date": ["earning date", "date", "work date"],
            "pay_category": ["pay category", "earnings category", "earning name", "pay item"],
            "hours": ["hours", "units", "quantity"],
            "rate": ["rate", "hourly rate", "unit rate"],
            "amount": ["amount", "earnings", "gross amount", "value"],
        },
    },
    "pay_runs": {
        "required": ["pay_period_start", "pay_period_end"],
        "recommended": ["pay_run_id", "status"],
        "aliases": {
            "pay_run_id": ["pay run id", "payrun id", "run id"],
            "pay_period_start": ["pay period start", "period start", "from date"],
            "pay_period_end": ["pay period end", "period end", "to date"],
            "status": ["status", "pay run status"],
        },
    },
    "industrial_instrument_history": {
        "required": ["employee_id", "effective_from", "instrument_type"],
        "recommended": ["effective_to", "instrument_name", "award_code", "document_reference"],
        "aliases": {
            "employee_id": ["employee id", "employee number"],
            "effective_from": ["effective from", "start date"],
            "effective_to": ["effective to", "end date"],
            "instrument_type": ["instrument type", "coverage type", "award or agreement"],
            "instrument_name": ["instrument name", "award name", "agreement name"],
            "award_code": ["award code", "modern award code"],
            "document_reference": ["document reference", "evidence reference", "reference"],
        },
    },
    "part_time_patterns": {
        "required": ["employee_id", "effective_from", "weekday", "start_time", "end_time", "guaranteed_hours"],
        "recommended": ["effective_to", "agreement_reference"],
        "aliases": {
            "employee_id": ["employee id", "employee number"],
            "effective_from": ["effective from", "start date"],
            "effective_to": ["effective to", "end date"],
            "weekday": ["weekday", "day", "day of week"],
            "start_time": ["start time", "agreed start"],
            "end_time": ["end time", "agreed end"],
            "guaranteed_hours": ["guaranteed hours", "agreed hours", "hours"],
            "agreement_reference": ["agreement reference", "evidence reference", "reference"],
        },
    },
    "part_time_variations": {
        "required": ["employee_id", "shift_date", "start_time", "end_time"],
        "recommended": ["agreement_reference"],
        "aliases": {
            "employee_id": ["employee id", "employee number"],
            "shift_date": ["shift date", "date"],
            "start_time": ["start time", "varied start"],
            "end_time": ["end time", "varied end"],
            "agreement_reference": ["agreement reference", "evidence reference", "reference"],
        },
    },
    "public_holiday_overrides": {
        "required": ["state", "holiday_date", "holiday_name"],
        "recommended": ["holiday_location_key", "holiday_scope", "source"],
        "aliases": {
            "state": ["state", "region"],
            "holiday_date": ["holiday date", "date"],
            "holiday_name": ["holiday name", "name"],
            "holiday_location_key": ["holiday location key", "location key"],
            "holiday_scope": ["holiday scope", "scope"],
            "source": ["source", "reference"],
        },
    },
    "overtime_rest_controls": {
        "required": ["employee_id", "shift_start", "employer_instructed_resume"],
        "recommended": ["timesheet_id", "evidence_reference"],
        "aliases": {
            "employee_id": ["employee id", "employee number"],
            "timesheet_id": ["timesheet id", "shift id"],
            "shift_start": ["shift start", "start datetime"],
            "employer_instructed_resume": ["employer instructed resume", "instructed resume", "return instructed"],
            "evidence_reference": ["evidence reference", "reference"],
        },
    },
    "meal_break_events": {
        "required": ["event_id", "employee_id", "timesheet_id", "mode"],
        "recommended": ["scheduled_break_start", "actual_break_start", "deducted_break_minutes", "paid_meal_minutes", "evidence_reference"],
        "aliases": {
            "event_id": ["event id", "record id"],
            "employee_id": ["employee id", "employee number"],
            "timesheet_id": ["timesheet id", "shift id"],
            "mode": ["mode", "meal break mode", "break type"],
            "scheduled_break_start": ["scheduled break start", "planned break"],
            "actual_break_start": ["actual break start", "break start"],
            "deducted_break_minutes": ["deducted break minutes", "break minutes deducted"],
            "paid_meal_minutes": ["paid meal minutes", "paid break minutes"],
            "evidence_reference": ["evidence reference", "reference"],
        },
    },
    "supplemental_events": {
        "required": ["event_id", "employee_id", "event_type"],
        "recommended": ["start_datetime", "end_datetime", "hours", "classification_code", "employment_type", "work_group", "state"],
        "aliases": {
            "event_id": ["event id", "record id"],
            "employee_id": ["employee id", "employee number"],
            "event_type": ["event type", "type"],
            "start_datetime": ["start datetime", "start time"],
            "end_datetime": ["end datetime", "end time"],
            "hours": ["hours", "units"],
            "classification_code": ["classification code", "pay level code"],
            "employment_type": ["employment type", "employment status"],
            "work_group": ["work group", "award stream"],
            "state": ["state", "region"],
        },
    },
    "toil_register": {
        "required": ["agreement_id", "employee_id", "overtime_datetime", "overtime_hours", "written_agreement"],
        "recommended": ["agreement_date", "time_off_hours", "time_off_date", "payment_requested_date", "payment_date", "evidence_reference"],
        "aliases": {
            "agreement_id": ["agreement id", "toil id", "record id"],
            "employee_id": ["employee id", "employee number"],
            "overtime_datetime": ["overtime datetime", "overtime date", "overtime start"],
            "overtime_hours": ["overtime hours", "ot hours"],
            "written_agreement": ["written agreement", "agreement", "toil agreed"],
            "agreement_date": ["agreement date", "date agreed"],
            "time_off_hours": ["time off hours", "toil hours taken"],
            "time_off_date": ["time off date", "toil date"],
            "payment_requested_date": ["payment requested date", "request date"],
            "payment_date": ["payment date", "paid date"],
            "evidence_reference": ["evidence reference", "reference"],
        },
    },
    "pay_category_mapping": {
        "required": ["source_key", "treatment"],
        "recommended": ["source_label"],
        "aliases": {
            "source_key": ["source key", "pay category id", "category id", "pay category"],
            "source_label": ["source label", "pay category name", "category name", "label"],
            "treatment": ["treatment", "audit treatment", "classification"],
        },
    },
}

DATASET_ALIASES = {
    "employees": ["employees", "employee", "staff", "workers", "people"],
    "pay_details": ["pay details", "pay rates", "classifications", "award classifications"],
    "employment_history": ["employment history", "employment", "contracts", "job history"],
    "timesheets": ["timesheets", "time entries", "time and attendance", "shifts", "attendance"],
    "rostered_shifts": ["roster", "rostered shifts", "scheduled shifts", "schedule"],
    "payroll_earnings": ["payroll earnings", "earnings", "pay lines", "payroll detail", "payroll"],
    "pay_runs": ["pay runs", "payrun", "pay periods"],
    "industrial_instrument_history": ["industrial instrument", "award coverage", "agreements", "coverage history"],
    "part_time_patterns": ["part time patterns", "agreed hours", "part time agreement"],
    "part_time_variations": ["part time variations", "agreed variations", "variations"],
    "public_holiday_overrides": ["public holidays", "holiday overrides", "local holidays"],
    "overtime_rest_controls": ["overtime rest", "rest controls", "10 hour rest"],
    "meal_break_events": ["meal breaks", "meal break events", "worked through meals"],
    "supplemental_events": ["supplemental events", "allowances", "special events"],
    "toil_register": ["toil", "time off in lieu", "toil register"],
    "pay_category_mapping": ["pay category mapping", "pay categories", "earnings mapping"],
}


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _score(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:return 0.0
    if na == nb:return 1.0
    if na in nb or nb in na:return 0.92
    return SequenceMatcher(None, na, nb).ratio()


def _safe_path(root: Path, relative_or_absolute: str) -> Path:
    candidate = Path(relative_or_absolute)
    if not candidate.is_absolute():candidate = root / candidate
    resolved = candidate.resolve();root_resolved = root.resolve()
    try:resolved.relative_to(root_resolved)
    except ValueError as exc:raise ValueError(f"Source file must be under source_root: {candidate}") from exc
    return resolved


def scan_source_items(source_root: str | Path) -> pd.DataFrame:
    """List CSV files and Excel sheets available for mapping."""
    root = Path(source_root)
    if not root.exists():raise FileNotFoundError(f"Source folder does not exist: {root}")
    rows=[]
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("~$"):continue
        suffix=path.suffix.lower();rel=str(path.relative_to(root)).replace("\\", "/")
        try:
            if suffix == ".csv":
                df=pd.read_csv(path,nrows=25);rows.append({"file":rel,"sheet":None,"item_name":path.stem,"columns":list(df.columns),"sample_rows":len(df)})
            elif suffix in {".xlsx", ".xlsm"}:
                book=pd.ExcelFile(path)
                for sheet in book.sheet_names:
                    df=pd.read_excel(path,sheet_name=sheet,nrows=25);rows.append({"file":rel,"sheet":sheet,"item_name":f"{path.stem} {sheet}","columns":list(df.columns),"sample_rows":len(df)})
        except Exception as exc:rows.append({"file":rel,"sheet":None,"item_name":path.stem,"columns":[],"sample_rows":0,"error":str(exc)})
    return pd.DataFrame(rows)


def _best_column(columns: list[str], aliases: list[str], canonical: str) -> tuple[str | None, float]:
    candidates=aliases+[canonical,canonical.replace("_"," ")];best_col,best=None,0.0
    for col in columns:
        score=max(_score(col,alias) for alias in candidates)
        if score>best:best_col,best=col,score
    return best_col,best


def generate_mapping_draft(source_root: str | Path, minimum_field_confidence: float = 0.72) -> dict[str, Any]:
    inventory=scan_source_items(source_root);datasets={}
    for dataset,schema in CANONICAL_SCHEMAS.items():
        best_item=None;best_score=0.0
        for _,item in inventory.iterrows():
            columns=list(item.get("columns") or []);name_score=max(_score(item.get("item_name"),alias) for alias in DATASET_ALIASES.get(dataset,[dataset]));matched=0
            for field,aliases in schema.get("aliases",{}).items():
                _,field_score=_best_column(columns,aliases,field)
                if field_score>=minimum_field_confidence:matched+=1
            coverage=matched/max(1,len(schema.get("required",[])));score=(0.45*name_score)+(0.55*min(1.0,coverage))
            if score>best_score:best_item,best_score=item,score
        columns={};suggestions={}
        if best_item is not None:
            source_columns=list(best_item.get("columns") or [])
            for field in schema.get("required",[])+schema.get("recommended",[]):
                col,confidence=_best_column(source_columns,schema.get("aliases",{}).get(field,[]),field)
                if col and confidence>=minimum_field_confidence:columns[field]={"source":col}
                suggestions[field]={"suggested_source":col,"confidence":round(confidence,3)}
        enabled=bool(best_item is not None and best_score>=0.45);datasets[dataset]={"enabled":enabled,"source":({"file":best_item.get("file"),"sheet":best_item.get("sheet"),"header":0} if enabled else None),"columns":columns,"_suggestions":suggestions,"_dataset_confidence":round(best_score,3)}
    return {"version":1,"instructions":"Review every enabled dataset and field mapping before conversion. Ambiguous numeric dates are interpreted day-first. Delete _suggestions keys when satisfied if desired.","datasets":datasets}


def save_mapping_draft(source_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    draft=generate_mapping_draft(source_root);path=Path(output_path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(draft,indent=2),encoding="utf-8");return draft


def _read_descriptor(root: Path, descriptor: dict[str, Any]) -> pd.DataFrame:
    if not descriptor or not descriptor.get("file"):raise ValueError("Dataset source.file is required")
    path=_safe_path(root,descriptor["file"])
    if not path.exists():raise FileNotFoundError(f"Mapped source file not found: {path}")
    header=int(descriptor.get("header",0));skiprows=descriptor.get("skiprows")
    if path.suffix.lower()==".csv":return pd.read_csv(path,header=header,skiprows=skiprows)
    if path.suffix.lower() in {".xlsx",".xlsm"}:return pd.read_excel(path,sheet_name=descriptor.get("sheet",0),header=header,skiprows=skiprows)
    raise ValueError(f"Unsupported mapped source format: {path.name}")


def _blank_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().str.lower().isin(["", "nan", "none", "nat", "null"])


def _series_from_rule(df: pd.DataFrame, rule: Any, target: str) -> pd.Series:
    if isinstance(rule,str):rule={"source":rule}
    if not isinstance(rule,dict):raise ValueError(f"Mapping for {target} must be a source column name or object")
    if "constant" in rule:series=pd.Series([rule.get("constant")]*len(df),index=df.index)
    elif "concat" in rule:
        cols=list(rule.get("concat") or []);missing=[c for c in cols if c not in df.columns]
        if missing:raise ValueError(f"{target}: concat source column(s) missing: {missing}")
        sep=str(rule.get("separator"," "));series=df[cols].fillna("").astype(str).agg(sep.join,axis=1).str.strip()
    elif "date_source" in rule and "time_source" in rule:
        dcol,tcol=rule["date_source"],rule["time_source"];missing=[c for c in (dcol,tcol) if c not in df.columns]
        if missing:raise ValueError(f"{target}: date/time source column(s) missing: {missing}")
        series=parse_datetime_series(df[dcol].astype(str).str.strip()+" "+df[tcol].astype(str).str.strip())
    elif "sources" in rule:
        sources=list(rule.get("sources") or []);available=[c for c in sources if c in df.columns]
        if not available:raise ValueError(f"{target}: none of the coalesce source columns exist: {sources}")
        series=df[available[0]].copy()
        for col in available[1:]:series=series.where(~_blank_mask(series),df[col])
    elif "source" in rule:
        source=rule["source"]
        if source not in df.columns:raise ValueError(f"{target}: source column not found: {source}")
        series=df[source].copy()
    else:raise ValueError(f"{target}: mapping must specify source, sources, concat, date_source/time_source or constant")
    if rule.get("strip",True) and series.dtype=="object":series=series.map(lambda x:x.strip() if isinstance(x,str) else x)
    value_map=rule.get("value_map") or rule.get("map")
    if value_map:
        original=series.copy();mapped=series.map(value_map);series=mapped.where(mapped.notna(),original if bool(rule.get("keep_unmapped",True)) else None)
    if "default" in rule:series=series.where(~_blank_mask(series),rule.get("default"))
    dtype=str(rule.get("type") or "").lower()
    if dtype in {"string","str"}:series=series.where(series.isna(),series.astype(str))
    elif dtype in {"number","float","decimal"}:series=pd.to_numeric(series,errors="coerce")
    elif dtype in {"integer","int"}:series=pd.to_numeric(series,errors="coerce").astype("Int64")
    elif dtype in {"date","datetime"}:
        parsed=parse_datetime_series(series);series=parsed.dt.date if dtype=="date" else parsed
    elif dtype in {"boolean","bool"}:
        truthy={"true","t","yes","y","1","on"};falsy={"false","f","no","n","0","off"}
        def conv(value: Any):
            if pd.isna(value):return None
            text=str(value).strip().lower()
            if text in truthy:return True
            if text in falsy:return False
            return None
        series=series.map(conv)
    return series


def convert_source_files(source_root: str | Path,mapping: dict[str, Any] | str | Path,output_root: str | Path,*,write_workbook: bool = True,strict: bool = True) -> dict[str, Any]:
    """Convert arbitrary source exports to AuditHero's canonical file model."""
    source_root=Path(source_root);output_root=Path(output_root);output_root.mkdir(parents=True,exist_ok=True)
    if isinstance(mapping,(str,Path)):
        from .mapping_workbook import load_mapping
        mapping=load_mapping(mapping)
    if int(mapping.get("version",0))!=1:raise ValueError("Unsupported source mapping version; expected version 1")
    frames={};report_rows=[];errors=[]
    for dataset,config in (mapping.get("datasets") or {}).items():
        if dataset not in CANONICAL_SCHEMAS or not config or not config.get("enabled",False):continue
        try:
            raw=_read_descriptor(source_root,config.get("source") or {});out=pd.DataFrame(index=raw.index);column_rules=config.get("columns") or {};schema=CANONICAL_SCHEMAS[dataset];missing_rules=[field for field in schema.get("required",[]) if field not in column_rules]
            if missing_rules:raise ValueError(f"Required canonical field(s) are not mapped: {missing_rules}")
            for target,rule in column_rules.items():
                out[target]=_series_from_rule(raw,rule,target);blanks=int(_blank_mask(out[target]).sum());report_rows.append({"dataset":dataset,"target_field":target,"source_rule":json.dumps(rule,default=str) if isinstance(rule,dict) else str(rule),"rows":len(out),"blank_values":blanks,"status":"READY" if blanks==0 or target not in schema.get("required",[]) else "REVIEW_BLANK_REQUIRED_VALUES"})
            if config.get("drop_duplicates"):out=out.drop_duplicates(subset=list(config["drop_duplicates"]))
            out=normalize_canonical_frame(dataset,out);frames[dataset]=out.reset_index(drop=True);frames[dataset].to_csv(output_root/f"{dataset}.csv",index=False)
        except Exception as exc:
            errors.append(f"{dataset}: {type(exc).__name__}: {exc}");report_rows.append({"dataset":dataset,"target_field":"*","source_rule":"","rows":0,"blank_values":None,"status":f"ERROR: {exc}"})
    core_required=["employees","pay_details","employment_history","timesheets"];missing_datasets=[d for d in core_required if d not in frames or frames[d].empty]
    if missing_datasets:errors.append("Required canonical dataset(s) were not produced: "+", ".join(missing_datasets))
    report=pd.DataFrame(report_rows);report.to_csv(output_root/"conversion_report.csv",index=False);(output_root/"mapping_used.json").write_text(json.dumps(mapping,indent=2),encoding="utf-8")
    workbook_path=output_root/"audithero_input.xlsx"
    if write_workbook and frames:
        with pd.ExcelWriter(workbook_path,engine="openpyxl") as writer:
            guide=pd.DataFrame([["AuditHero canonical workbook generated by source mapping pipeline"],["Generated datasets",", ".join(sorted(frames))],["Date interpretation","Ambiguous numeric dates use Australian day-first order (DD-MM-YYYY / DD/MM/YYYY). ISO YYYY-MM-DD is also supported."],["Conversion report","See conversion_report.csv beside this workbook"],["Next step","Run AuditHero File Readiness before running an audit"]]);guide.to_excel(writer,sheet_name="README",header=False,index=False)
            for dataset,frame in frames.items():frame.to_excel(writer,sheet_name=dataset[:31],index=False)
    result={"frames":frames,"report":report,"errors":errors,"output_root":str(output_root),"workbook":str(workbook_path) if write_workbook else None}
    if errors and strict:raise ValueError("Source conversion failed:\n - "+"\n - ".join(errors))
    return result
