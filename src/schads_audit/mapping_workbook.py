from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

import pandas as pd

from .source_mapping import CANONICAL_SCHEMAS


SPECIAL_FILE_ROLES = ["CONTEXT_ONLY", "IGNORE"]


def _bool(value: Any, default: bool = False) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):return default
    if isinstance(value, bool):return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def _text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):return None
    text = str(value).strip();return text if text else None


def _split(value: Any) -> list[str]:
    text = _text(value)
    if not text:return []
    return [x.strip() for x in text.split(";") if x.strip()]


def _source_key(file: Any, sheet: Any) -> tuple[str | None, str | None]:return _text(file), _text(sheet)


def _inventory(draft: dict[str, Any]) -> list[dict[str, Any]]:
    rows = draft.get("_source_inventory") or [];cleaned=[]
    for row in rows:
        if not isinstance(row, dict):continue
        cleaned.append({"file": _text(row.get("file")), "sheet": _text(row.get("sheet")), "item_name": _text(row.get("item_name")), "sample_rows": row.get("sample_rows"), "columns": list(row.get("columns") or [])})
    return cleaned


def _detected_role_for_item(draft: dict[str, Any], file: str | None, sheet: str | None) -> tuple[str | None, float | None]:
    best_role, best_conf = None, -1.0
    for dataset, cfg in (draft.get("datasets") or {}).items():
        source = (cfg or {}).get("source") or {}
        if _source_key(source.get("file"), source.get("sheet")) != _source_key(file, sheet):continue
        confidence = float((cfg or {}).get("_dataset_confidence") or 0.0)
        if confidence > best_conf:best_role, best_conf = dataset, confidence
    return best_role, (round(best_conf, 3) if best_role else None)


def draft_to_field_table(draft: dict[str, Any]) -> pd.DataFrame:
    rows=[]
    for dataset, schema in CANONICAL_SCHEMAS.items():
        cfg=(draft.get("datasets") or {}).get(dataset) or {};source=cfg.get("source") or {};suggestions=cfg.get("_suggestions") or {};fields=list(dict.fromkeys(schema.get("required", []) + schema.get("recommended", [])))
        for field in fields:
            rule=(cfg.get("columns") or {}).get(field) or {}
            if isinstance(rule,str):rule={"source":rule}
            suggestion=suggestions.get(field) or {}
            rows.append({"dataset":dataset,"enabled":bool(cfg.get("enabled",False)),"source_file":source.get("file"),"source_sheet":source.get("sheet"),"header_row":source.get("header",0),"target_field":field,"required":field in schema.get("required",[]),"source_field":rule.get("source") or suggestion.get("suggested_source"),"coalesce_fields":";".join(rule.get("sources") or []),"concat_fields":";".join(rule.get("concat") or []),"separator":rule.get("separator"," "),"date_source":rule.get("date_source"),"time_source":rule.get("time_source"),"constant":rule.get("constant"),"data_type":rule.get("type"),"default":rule.get("default"),"keep_unmapped":rule.get("keep_unmapped",True),"confidence":suggestion.get("confidence"),"notes":""})
    return pd.DataFrame(rows)


def draft_to_file_context_table(draft: dict[str, Any]) -> pd.DataFrame:
    rows=[]
    for item in _inventory(draft):
        role,confidence=_detected_role_for_item(draft,item["file"],item["sheet"]);rows.append({"source_file":item["file"],"source_sheet":item["sheet"],"detected_role":role,"detected_confidence":confidence,"selected_role":role or "CONTEXT_ONLY","use_as_primary_source":bool(role),"evidence_purpose":"","period_start":"","period_end":"","document_status":"","notes":""})
    return pd.DataFrame(rows)


def draft_to_preview_table(draft: dict[str, Any]) -> pd.DataFrame:
    rows=[]
    for dataset,schema in CANONICAL_SCHEMAS.items():
        cfg=(draft.get("datasets") or {}).get(dataset) or {};source=cfg.get("source") or {};mapped=cfg.get("columns") or {};required=list(schema.get("required",[]));missing=[f for f in required if f not in mapped];rows.append({"dataset":dataset,"detected":bool(cfg.get("enabled",False)),"source_file":source.get("file"),"source_sheet":source.get("sheet"),"confidence":cfg.get("_dataset_confidence"),"mapped_fields":len(mapped),"required_fields":len(required),"missing_required_fields":", ".join(missing),"preview_status":"READY_TO_REVIEW" if cfg.get("enabled") and not missing else ("MAPPING_INCOMPLETE" if cfg.get("enabled") else "NOT_DETECTED")})
    return pd.DataFrame(rows)


def _excel_lists(draft: dict[str, Any]) -> dict[str,list[str]]:
    inventory=_inventory(draft);files=sorted({str(x["file"]) for x in inventory if x.get("file")});sheets=sorted({str(x["sheet"]) for x in inventory if x.get("sheet")});columns=sorted({str(c) for x in inventory for c in (x.get("columns") or []) if str(c).strip()})
    if not columns:
        fields=draft_to_field_table(draft)
        for col in ("source_field","date_source","time_source"):
            if col in fields.columns:columns.extend(fields[col].dropna().astype(str).tolist())
        columns=sorted(set(columns))
    all_fields=sorted({field for schema in CANONICAL_SCHEMAS.values() for field in schema.get("required",[])+schema.get("recommended",[])})
    return {"datasets":list(CANONICAL_SCHEMAS),"roles":list(CANONICAL_SCHEMAS)+SPECIAL_FILE_ROLES,"files":files,"sheets":sheets,"columns":columns,"fields":all_fields,"types":["string","number","integer","date","datetime","boolean"],"bools":["TRUE","FALSE"]}


def _add_range_validation(workbook, worksheet, cell_range: str, values: list[str], list_name: str, *, allow_blank: bool=True)->None:
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.workbook.defined_name import DefinedName
    if not values:return
    lists=workbook["_lists"];start_col=lists.max_column+1 if lists.max_column else 1;lists.cell(1,start_col,list_name)
    for idx,value in enumerate(values,start=2):lists.cell(idx,start_col,value)
    letter=lists.cell(1,start_col).column_letter;attr_text=f"'_lists'!${letter}$2:${letter}${len(values)+1}";safe_name=re.sub(r"[^A-Za-z0-9_.]","_",list_name)
    if safe_name and safe_name[0].isdigit():safe_name="L_"+safe_name
    workbook.defined_names.add(DefinedName(safe_name,attr_text=attr_text));validation=DataValidation(type="list",formula1=f"={safe_name}",allow_blank=allow_blank);validation.error="Select a value from the AuditHero dropdown list.";validation.errorTitle="Invalid mapping value";validation.prompt="Select a controlled value; do not type an internal schema key.";validation.promptTitle="AuditHero mapping";validation.showErrorMessage=True;validation.showInputMessage=True;worksheet.add_data_validation(validation);validation.add(cell_range)


def write_mapping_workbook(draft:dict[str,Any],path:str|Path)->Path:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);fields=draft_to_field_table(draft);file_context=draft_to_file_context_table(draft);preview=draft_to_preview_table(draft);values=pd.DataFrame(columns=["dataset","target_field","source_value","target_value","notes"])
    instructions=pd.DataFrame([["AuditHero Advanced Mapping / Context Workbook"],["Purpose","Optional correction layer. The uploaded source files remain the audit evidence; this workbook only tells AuditHero how to interpret them."],["Date format","Ambiguous numeric dates are interpreted in Australian day-first order (DD-MM-YYYY, DD/MM/YYYY or DD.MM.YYYY). ISO YYYY-MM-DD remains supported."],["Normal workflow","Upload CSV/XLSX files, review AuditHero's preview, and continue when the interpretation is correct."],["When to use this workbook","Use it when a file role or field was missed, a source column was mapped incorrectly, or extra context is needed for reconciliation and audit evidence."],["file_context","Confirm or correct what each uploaded file/sheet represents. CONTEXT_ONLY keeps the item as evidence but prevents it being used as a canonical source; IGNORE excludes it from mapping."],["field_mapping","Correct source-to-AuditHero field mappings. Use dropdowns rather than typing source headings where available."],["value_mapping","Translate source values into controlled AuditHero values when needed."],["preview","Shows the automatic interpretation that existed when this correction workbook was generated."],["Primary source","Only one primary source may be selected for a canonical dataset. Duplicate primary selections are rejected."],["Safety","No formulas or Python expressions are executed from this workbook. Original source files are never changed. Missing required mapped fields fail closed during conversion."],["Not mandatory","If automatic intake is correct and sufficient evidence is present, no Advanced Mapping workbook is required to calculate supported outcomes."]])
    with pd.ExcelWriter(path,engine="openpyxl") as writer:
        instructions.to_excel(writer,sheet_name="README",header=False,index=False);preview.to_excel(writer,sheet_name="preview",index=False);file_context.to_excel(writer,sheet_name="file_context",index=False);fields.to_excel(writer,sheet_name="field_mapping",index=False);values.to_excel(writer,sheet_name="value_mapping",index=False)
    from openpyxl import load_workbook
    wb=load_workbook(path);lists_ws=wb.create_sheet("_lists");lists_ws.sheet_state="hidden";lists=_excel_lists(draft);ws=wb["field_mapping"];ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
    for col,width in {"A":28,"B":10,"C":34,"D":26,"E":12,"F":34,"G":10,"H":34,"I":34,"J":34,"K":12,"L":30,"M":30,"N":22,"O":14,"P":18,"Q":16,"R":12,"S":42}.items():ws.column_dimensions[col].width=width
    max_row=max(2,ws.max_row);_add_range_validation(wb,ws,f"A2:A{max_row}",lists["datasets"],"datasets",allow_blank=False);_add_range_validation(wb,ws,f"B2:B{max_row}",lists["bools"],"enabled_values");_add_range_validation(wb,ws,f"C2:C{max_row}",lists["files"],"source_files");_add_range_validation(wb,ws,f"D2:D{max_row}",lists["sheets"],"source_sheets")
    for col in ("H","L","M"):_add_range_validation(wb,ws,f"{col}2:{col}{max_row}",lists["columns"],f"source_columns_{col}")
    _add_range_validation(wb,ws,f"O2:O{max_row}",lists["types"],"data_types");_add_range_validation(wb,ws,f"Q2:Q{max_row}",lists["bools"],"keep_unmapped_values")
    context=wb["file_context"];context.freeze_panes="A2";context.auto_filter.ref=context.dimensions
    for col,width in {"A":34,"B":26,"C":28,"D":20,"E":30,"F":22,"G":48,"H":16,"I":16,"J":24,"K":48}.items():context.column_dimensions[col].width=width
    max_context=max(2,context.max_row);_add_range_validation(wb,context,f"E2:E{max_context}",lists["roles"],"file_roles");_add_range_validation(wb,context,f"F2:F{max_context}",lists["bools"],"primary_source_values")
    pws=wb["preview"];pws.freeze_panes="A2";pws.auto_filter.ref=pws.dimensions
    for col,width in {"A":30,"B":12,"C":34,"D":24,"E":12,"F":14,"G":16,"H":54,"I":24}.items():pws.column_dimensions[col].width=width
    vm=wb["value_mapping"];vm.freeze_panes="A2";vm.auto_filter.ref=vm.dimensions
    for col,width in {"A":28,"B":34,"C":30,"D":30,"E":40}.items():vm.column_dimensions[col].width=width
    _add_range_validation(wb,vm,"A2:A1000",lists["datasets"],"value_datasets");_add_range_validation(wb,vm,"B2:B1000",lists["fields"],"value_target_fields");readme=wb["README"];readme.column_dimensions["A"].width=30;readme.column_dimensions["B"].width=118;wb.save(path);return path


def load_mapping_workbook(path:str|Path)->dict[str,Any]:
    path=Path(path);fields=pd.read_excel(path,sheet_name="field_mapping")
    try:values=pd.read_excel(path,sheet_name="value_mapping")
    except ValueError:values=pd.DataFrame(columns=["dataset","target_field","source_value","target_value"])
    try:file_context=pd.read_excel(path,sheet_name="file_context")
    except ValueError:file_context=pd.DataFrame()
    primary_sources={};non_source_items=set();context_records=[]
    if not file_context.empty:
        seen_primary={}
        for _,row in file_context.iterrows():
            role=_text(row.get("selected_role")) or "CONTEXT_ONLY"
            if role not in CANONICAL_SCHEMAS and role not in SPECIAL_FILE_ROLES:raise ValueError(f"Unsupported file_context selected_role: {role}")
            source_key=_source_key(row.get("source_file"),row.get("source_sheet"))
            if not source_key[0]:continue
            primary=_bool(row.get("use_as_primary_source"),False)
            if role in SPECIAL_FILE_ROLES:non_source_items.add(source_key);primary=False
            elif primary:
                if role in seen_primary and seen_primary[role]!=source_key:raise ValueError(f"Multiple primary sources were selected for {role}: {seen_primary[role]} and {source_key}. Select one primary source.")
                seen_primary[role]=source_key;primary_sources[role]={"file":source_key[0],"sheet":source_key[1],"header":0}
            context_records.append({"source_file":source_key[0],"source_sheet":source_key[1],"selected_role":role,"use_as_primary_source":primary,"evidence_purpose":_text(row.get("evidence_purpose")),"period_start":_text(row.get("period_start")),"period_end":_text(row.get("period_end")),"document_status":_text(row.get("document_status")),"notes":_text(row.get("notes"))})
    datasets={};allowed_fields={d:set(s.get("required",[])+s.get("recommended",[])) for d,s in CANONICAL_SCHEMAS.items()}
    for dataset,group in fields.groupby("dataset",dropna=True):
        dataset=str(dataset).strip()
        if dataset not in CANONICAL_SCHEMAS:continue
        first=group.iloc[0];original_source={"file":_text(first.get("source_file")),"sheet":_text(first.get("source_sheet")),"header":int(first.get("header_row") or 0)};source=primary_sources.get(dataset) or original_source;enabled=_bool(first.get("enabled"),False)
        if dataset in primary_sources:enabled=True
        elif _source_key(original_source.get("file"),original_source.get("sheet")) in non_source_items:enabled=False
        cfg={"enabled":enabled,"source":source,"columns":{}}
        for _,row in group.iterrows():
            target=_text(row.get("target_field"))
            if not target or target not in allowed_fields[dataset]:continue
            rule={}
            if _text(row.get("source_field")):rule["source"]=_text(row.get("source_field"))
            elif _split(row.get("coalesce_fields")):rule["sources"]=_split(row.get("coalesce_fields"))
            elif _split(row.get("concat_fields")):rule["concat"]=_split(row.get("concat_fields"));rule["separator"]=_text(row.get("separator")) or " "
            elif _text(row.get("date_source")) and _text(row.get("time_source")):rule["date_source"]=_text(row.get("date_source"));rule["time_source"]=_text(row.get("time_source"));rule["dayfirst"]=True
            elif _text(row.get("constant")) is not None:rule["constant"]=row.get("constant")
            else:continue
            dtype=_text(row.get("data_type"))
            if dtype:
                rule["type"]=dtype
                if dtype.lower() in {"date","datetime"}:rule["dayfirst"]=True
            default=row.get("default")
            if default is not None and not (isinstance(default,float) and pd.isna(default)):rule["default"]=default
            rule["keep_unmapped"]=_bool(row.get("keep_unmapped"),True)
            if not values.empty and {"dataset","target_field"}.issubset(values.columns):
                subset=values[(values["dataset"].astype(str).str.strip()==dataset)&(values["target_field"].astype(str).str.strip()==target)];value_map={}
                for _,vrow in subset.iterrows():
                    source_value=vrow.get("source_value");target_value=vrow.get("target_value")
                    if pd.notna(source_value):value_map[source_value]=target_value
                if value_map:rule["value_map"]=value_map
            cfg["columns"][target]=rule
        datasets[dataset]=cfg
    return {"version":1,"datasets":datasets,"file_context":context_records,"source":str(path)}


def load_mapping(path:str|Path)->dict[str,Any]:
    path=Path(path)
    if path.suffix.lower()==".json":return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".xlsx",".xlsm"}:return load_mapping_workbook(path)
    raise ValueError("Mapping must be a .json, .xlsx or .xlsm file")
