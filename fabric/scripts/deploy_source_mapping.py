#!/usr/bin/env python3
"""Deploy AuditHero's source-mapping and mapped-import pipelines to Fabric.

The normal operator flow is intentionally UI-driven:
1. Build a draft mapping workbook from the organisation's raw exports.
2. Review/edit that workbook in Excel and upload it as ``source_mapping.xlsx``.
3. Run the conversion pipeline by itself, or run the combined mapped-import audit
   pipeline to convert, audit and refresh Power BI in one operation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from deploy_fabric import FabricClient, access_token, notebook_activity, literal, expression

ROOT = Path(__file__).resolve().parents[2]
FABRIC = ROOT / "fabric"


def draft_pipeline(workspace_id: str, notebook_id: str, defaults: dict):
    return {
        "properties": {
            "description": "Inspect uploaded CSV/XLSX exports and create an editable AuditHero source-mapping workbook.",
            "parameters": {
                "source_root": {"type": "string", "defaultValue": defaults["source_root"]},
                "draft_path": {"type": "string", "defaultValue": defaults["draft_path"]},
                "overwrite": {"type": "string", "defaultValue": "false"},
            },
            "activities": [
                notebook_activity(
                    "Inspect Files and Build Mapping Draft",
                    notebook_id,
                    workspace_id,
                    {
                        "source_root": expression("@pipeline().parameters.source_root"),
                        "draft_path": expression("@pipeline().parameters.draft_path"),
                        "overwrite": expression("@pipeline().parameters.overwrite"),
                    },
                )
            ],
        }
    }


def conversion_pipeline(workspace_id: str, notebook_id: str, defaults: dict):
    return {
        "properties": {
            "description": "Convert organisation-specific CSV/XLSX exports into AuditHero canonical input files and run File Readiness.",
            "parameters": {
                "source_root": {"type": "string", "defaultValue": defaults["source_root"]},
                "mapping_path": {"type": "string", "defaultValue": defaults["mapping_path"]},
                "output_root": {"type": "string", "defaultValue": defaults["output_root"]},
                "strict": {"type": "string", "defaultValue": "true"},
            },
            "activities": [
                notebook_activity(
                    "Convert Source Files and Validate",
                    notebook_id,
                    workspace_id,
                    {
                        "source_root": expression("@pipeline().parameters.source_root"),
                        "mapping_path": expression("@pipeline().parameters.mapping_path"),
                        "output_root": expression("@pipeline().parameters.output_root"),
                        "strict": expression("@pipeline().parameters.strict"),
                    },
                )
            ],
        }
    }


def mapped_import_audit_pipeline(
    workspace_id: str,
    convert_notebook_id: str,
    audit_notebook_id: str,
    bi_notebook_id: str,
    defaults: dict,
    bi_params: dict,
):
    """Return the Fabric pipeline used after a source mapping has been approved."""
    return {
        "properties": {
            "description": "Convert raw mapped CSV/XLSX exports, run the SCHADS audit and refresh the AuditHero Power BI model/report.",
            "parameters": {
                "source_root": {"type": "string", "defaultValue": defaults["source_root"]},
                "mapping_path": {"type": "string", "defaultValue": defaults["mapping_path"]},
                "output_root": {"type": "string", "defaultValue": defaults["output_root"]},
                "strict": {"type": "string", "defaultValue": "true"},
                "start_date": {"type": "string", "defaultValue": defaults["start_date"]},
                "end_date": {"type": "string", "defaultValue": defaults["end_date"]},
            },
            "activities": [
                notebook_activity(
                    "Convert Mapped Source Files",
                    convert_notebook_id,
                    workspace_id,
                    {
                        "source_root": expression("@pipeline().parameters.source_root"),
                        "mapping_path": expression("@pipeline().parameters.mapping_path"),
                        "output_root": expression("@pipeline().parameters.output_root"),
                        "strict": expression("@pipeline().parameters.strict"),
                    },
                ),
                notebook_activity(
                    "Run Audit on Converted Files",
                    audit_notebook_id,
                    workspace_id,
                    {
                        "input_root": expression("@pipeline().parameters.output_root"),
                        "start_date": expression("@pipeline().parameters.start_date"),
                        "end_date": expression("@pipeline().parameters.end_date"),
                    },
                    depends=["Convert Mapped Source Files"],
                ),
                notebook_activity(
                    "Refresh Direct Lake and Power BI",
                    bi_notebook_id,
                    workspace_id,
                    {k: literal(v) for k, v in bi_params.items()},
                    depends=["Run Audit on Converted Files"],
                ),
            ],
        }
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(FABRIC / "config" / "fabric.json"))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    ws = cfg["workspace_id"]
    source_cfg = cfg.get("source_mapping", {})
    hist = cfg.get("historical_defaults", {})
    defaults = {
        "source_root": source_cfg.get("source_root", "/lakehouse/default/Files/import/raw"),
        "draft_path": source_cfg.get("draft_path", "/lakehouse/default/Files/import/source_mapping_draft.xlsx"),
        "mapping_path": source_cfg.get("mapping_path", "/lakehouse/default/Files/import/source_mapping.xlsx"),
        "output_root": source_cfg.get("output_root", "/lakehouse/default/Files/input"),
        "start_date": hist.get("start_date", "2023-07-01"),
        "end_date": hist.get("end_date", "2026-06-30"),
    }

    client = FabricClient(ws, access_token())
    lakehouse = client.find("Lakehouse", cfg.get("lakehouse_name", "AuditHero_Lakehouse"))
    environment = client.find("Environment", cfg.get("environment_name", "AuditHero_Environment"))
    audit_notebook = client.find("Notebook", "AuditHero - Audit Uploaded CSV Excel")
    bi_notebook = client.find("Notebook", "AuditHero - Build BI")
    if not lakehouse or not environment:
        raise RuntimeError("AuditHero Lakehouse/Environment not found. Complete the base Fabric installation first.")
    if not audit_notebook or not bi_notebook:
        raise RuntimeError("AuditHero file-audit or BI notebook not found. Deploy the standard file-source path first.")

    draft_params = {
        "source_root": defaults["source_root"],
        "draft_path": defaults["draft_path"],
        "overwrite": "false",
    }
    convert_params = {
        "source_root": defaults["source_root"],
        "mapping_path": defaults["mapping_path"],
        "output_root": defaults["output_root"],
        "strict": "true",
    }

    draft_code = (FABRIC / "notebooks" / "03c_source_mapping_draft.py").read_text(encoding="utf-8")
    convert_code = (FABRIC / "notebooks" / "03d_convert_source_files.py").read_text(encoding="utf-8")
    draft_notebook = client.upsert_notebook(
        "AuditHero - Build Source Mapping Workbook", draft_code, lakehouse, environment, draft_params
    )
    convert_notebook = client.upsert_notebook(
        "AuditHero - Convert Source Files", convert_code, lakehouse, environment, convert_params
    )

    workspace_name = cfg.get("workspace_name") or ws
    lakehouse_name = cfg.get("lakehouse_name", "AuditHero_Lakehouse")
    semantic_model_name = cfg.get("semantic_model_name", "AuditHero - SCHADS Payroll Compliance")
    bi_params = {
        "workspace_name": workspace_name,
        "lakehouse_name": lakehouse_name,
        "semantic_model_name": semantic_model_name,
        "report_name": cfg.get("report_name", semantic_model_name),
    }

    draft_item = client.upsert_pipeline(
        source_cfg.get("draft_pipeline_name", "AuditHero - Build Source Mapping Workbook"),
        draft_pipeline(ws, draft_notebook["id"], defaults),
    )
    convert_item = client.upsert_pipeline(
        source_cfg.get("conversion_pipeline_name", "AuditHero - Convert Source Files"),
        conversion_pipeline(ws, convert_notebook["id"], defaults),
    )
    mapped_item = client.upsert_pipeline(
        source_cfg.get("mapped_audit_pipeline_name", "AuditHero - Convert Mapped Files and Run Audit"),
        mapped_import_audit_pipeline(
            ws,
            convert_notebook["id"],
            audit_notebook["id"],
            bi_notebook["id"],
            defaults,
            bi_params,
        ),
    )

    state_path = FABRIC / "deployment_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    state.update(
        {
            "source_mapping_draft_notebook_id": draft_notebook["id"],
            "source_mapping_convert_notebook_id": convert_notebook["id"],
            "source_mapping_draft_pipeline_id": draft_item["id"],
            "source_mapping_conversion_pipeline_id": convert_item["id"],
            "source_mapping_mapped_audit_pipeline_id": mapped_item["id"],
        }
    )
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print("AuditHero source-mapping pipelines deployed.")
    print("1. Upload raw exports under:", defaults["source_root"])
    print("2. Run 'AuditHero - Build Source Mapping Workbook'.")
    print("3. Edit/upload the approved mapping as:", defaults["mapping_path"])
    print("4. Run 'AuditHero - Convert Mapped Files and Run Audit' for normal operation.")
    print("   Use 'AuditHero - Convert Source Files' when you only want to test the conversion/readiness stage.")


if __name__ == "__main__":
    main()
