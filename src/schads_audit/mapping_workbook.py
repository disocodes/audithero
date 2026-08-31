from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from .source_mapping import CANONICAL_SCHEMAS


def _bool(value: Any, default: bool = False) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def _text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text if text else None


def _split(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    return [x.strip() for x in text.split(";") if x.strip()]


def draft_to_field_table(draft: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dataset, schema in CANONICAL_SCHEMAS.items():
        cfg = (draft.get("datasets") or {}).get(dataset) or {}
        source = cfg.get("source") or {}
        suggestions = cfg.get("_suggestions") or {}
        fields = list(dict.fromkeys(schema.get("required", []) + schema.get("recommended", [])))
        for field in fields:
            rule = (cfg.get("columns") or {}).get(field) or {}
            if isinstance(rule, str):
                rule = {"source": rule}
            suggestion = suggestions.get(field) or {}
            rows.append({
                "dataset": dataset,
                "enabled": bool(cfg.get("enabled", False)),
                "source_file": source.get("file"),
                "source_sheet": source.get("sheet"),
                "header_row": source.get("header", 0),
                "target_field": field,
                "required": field in schema.get("required", []),
                "source_field": rule.get("source") or suggestion.get("suggested_source"),
                "coalesce_fields": ";".join(rule.get("sources") or []),
                "concat_fields": ";".join(rule.get("concat") or []),
                "separator": rule.get("separator", " "),
                "date_source": rule.get("date_source"),
                "time_source": rule.get("time_source"),
                "constant": rule.get("constant"),
                "data_type": rule.get("type"),
                "default": rule.get("default"),
                "keep_unmapped": rule.get("keep_unmapped", True),
                "confidence": suggestion.get("confidence"),
                "notes": "",
            })
    return pd.DataFrame(rows)


def write_mapping_workbook(draft: dict[str, Any], path: str | Path) -> Path:
    """Write a human-editable Excel mapping workbook from an auto-generated draft."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = draft_to_field_table(draft)
    values = pd.DataFrame(columns=["dataset", "target_field", "source_value", "target_value", "notes"])
    instructions = pd.DataFrame([
        ["AuditHero Source Mapping Workbook"],
        ["Purpose", "Match columns from your payroll/HR/timekeeping exports to AuditHero's standard fields."],
        ["How to use", "Review the field_mapping sheet, correct source file/sheet/column matches, add value translations if needed, save as source_mapping.xlsx, then run Convert Source Files."],
        ["enabled", "TRUE means this canonical dataset will be produced. Disable datasets you are not supplying."],
        ["source_file", "File path relative to the raw source folder, for example payroll_export.xlsx or timesheets.csv."],
        ["source_sheet", "Excel sheet name. Leave blank for CSV."],
        ["source_field", "One source column copied to the target field."],
        ["coalesce_fields", "Alternative source columns separated by semicolons. AuditHero uses the first non-blank value."],
        ["concat_fields", "Source columns separated by semicolons to join, for example First Name;Last Name."],
        ["date_source/time_source", "Use when date and time are in separate columns and must become one datetime."],
        ["constant", "Use the same value for every row, for example DISABILITY_SERVICES."],
        ["data_type", "Optional: string, number, integer, date, datetime or boolean."],
        ["default", "Value used when the mapped source value is blank."],
        ["value_mapping", "Use the value_mapping sheet to translate source values, for example Permanent Full Time -> FULL_TIME."],
        ["Safety", "No formulas or Python expressions are executed from this workbook. Unmapped required fields stop conversion."],
    ])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        instructions.to_excel(writer, sheet_name="README", header=False, index=False)
        fields.to_excel(writer, sheet_name="field_mapping", index=False)
        values.to_excel(writer, sheet_name="value_mapping", index=False)

    from openpyxl import load_workbook
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = load_workbook(path)
    ws = wb["field_mapping"]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    widths = {
        "A": 28, "B": 10, "C": 30, "D": 24, "E": 12, "F": 34, "G": 10,
        "H": 32, "I": 32, "J": 32, "K": 12, "L": 28, "M": 28, "N": 22,
        "O": 14, "P": 18, "Q": 16, "R": 12, "S": 40,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    dv_bool = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
    dv_type = DataValidation(type="list", formula1='"string,number,integer,date,datetime,boolean"', allow_blank=True)
    ws.add_data_validation(dv_bool)
    ws.add_data_validation(dv_type)
    dv_bool.add(f"B2:B{max(2, ws.max_row)}")
    dv_type.add(f"O2:O{max(2, ws.max_row)}")
    vm = wb["value_mapping"]
    vm.freeze_panes = "A2"
    vm.auto_filter.ref = vm.dimensions
    for col, width in {"A": 28, "B": 34, "C": 30, "D": 30, "E": 40}.items():
        vm.column_dimensions[col].width = width
    readme = wb["README"]
    readme.column_dimensions["A"].width = 28
    readme.column_dimensions["B"].width = 110
    wb.save(path)
    return path


def load_mapping_workbook(path: str | Path) -> dict[str, Any]:
    """Convert an edited mapping workbook into the version-1 mapping dictionary."""
    path = Path(path)
    fields = pd.read_excel(path, sheet_name="field_mapping")
    try:
        values = pd.read_excel(path, sheet_name="value_mapping")
    except ValueError:
        values = pd.DataFrame(columns=["dataset", "target_field", "source_value", "target_value"])

    datasets: dict[str, Any] = {}
    for dataset, group in fields.groupby("dataset", dropna=True):
        dataset = str(dataset).strip()
        if dataset not in CANONICAL_SCHEMAS:
            continue
        first = group.iloc[0]
        cfg: dict[str, Any] = {
            "enabled": _bool(first.get("enabled"), False),
            "source": {
                "file": _text(first.get("source_file")),
                "sheet": _text(first.get("source_sheet")),
                "header": int(first.get("header_row") or 0),
            },
            "columns": {},
        }
        for _, row in group.iterrows():
            target = _text(row.get("target_field"))
            if not target:
                continue
            rule: dict[str, Any] = {}
            if _text(row.get("source_field")):
                rule["source"] = _text(row.get("source_field"))
            elif _split(row.get("coalesce_fields")):
                rule["sources"] = _split(row.get("coalesce_fields"))
            elif _split(row.get("concat_fields")):
                rule["concat"] = _split(row.get("concat_fields"))
                rule["separator"] = _text(row.get("separator")) or " "
            elif _text(row.get("date_source")) and _text(row.get("time_source")):
                rule["date_source"] = _text(row.get("date_source"))
                rule["time_source"] = _text(row.get("time_source"))
            elif _text(row.get("constant")) is not None:
                rule["constant"] = row.get("constant")
            else:
                continue
            dtype = _text(row.get("data_type"))
            if dtype:
                rule["type"] = dtype
            default = row.get("default")
            if default is not None and not (isinstance(default, float) and pd.isna(default)):
                rule["default"] = default
            rule["keep_unmapped"] = _bool(row.get("keep_unmapped"), True)

            if not values.empty:
                subset = values[
                    (values["dataset"].astype(str).str.strip() == dataset)
                    & (values["target_field"].astype(str).str.strip() == target)
                ]
                value_map = {}
                for _, vrow in subset.iterrows():
                    source_value = vrow.get("source_value")
                    target_value = vrow.get("target_value")
                    if pd.notna(source_value):
                        value_map[source_value] = target_value
                if value_map:
                    rule["value_map"] = value_map
            cfg["columns"][target] = rule
        datasets[dataset] = cfg
    return {"version": 1, "datasets": datasets, "source": str(path)}


def load_mapping(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return load_mapping_workbook(path)
    raise ValueError("Mapping must be a .json, .xlsx or .xlsm file")
