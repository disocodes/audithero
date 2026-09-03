#!/usr/bin/env python3
"""Deploy AuditHero uploaded-file audit paths in Microsoft Fabric.

The primary path automatically identifies ordinary CSV/XLSX timesheet and employee
rate files. The canonical/readiness path remains available for advanced imports.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from deploy_fabric import FabricClient, access_token, notebook_activity, literal, expression

ROOT = Path(__file__).resolve().parents[2]
FABRIC = ROOT / "fabric"


def auto_file_pipeline(
    workspace_id,
    intake_notebook_id,
    audit_notebook_id,
    bi_notebook_id,
    auto_cfg,
    bi_params,
):
    source_root = auto_cfg.get("source_root", "/lakehouse/default/Files/import/raw")
    output_root = auto_cfg.get("output_root", "/lakehouse/default/Files/auto_input")
    return {
        "properties": {
            "description": "Automatically prepare ordinary CSV/XLSX files, run the complete SCHADS audit and refresh the AuditHero report",
            "parameters": {
                "source_root": {"type": "string", "defaultValue": source_root},
                "start_date": {"type": "string", "defaultValue": ""},
                "end_date": {"type": "string", "defaultValue": ""},
            },
            "activities": [
                notebook_activity(
                    "Auto Prepare Uploaded Files",
                    intake_notebook_id,
                    workspace_id,
                    {
                        "source_root": expression("@pipeline().parameters.source_root"),
                        "output_root": literal(output_root),
                        "start_date": expression("@pipeline().parameters.start_date"),
                        "end_date": expression("@pipeline().parameters.end_date"),
                    },
                ),
                notebook_activity(
                    "Run Complete SCHADS Audit",
                    audit_notebook_id,
                    workspace_id,
                    {
                        "input_root": literal(output_root),
                        "start_date": expression("@pipeline().parameters.start_date"),
                        "end_date": expression("@pipeline().parameters.end_date"),
                        "run_type": literal("AUTO_FILE"),
                    },
                    depends=["Auto Prepare Uploaded Files"],
                ),
                notebook_activity(
                    "Refresh Direct Lake and Power BI",
                    bi_notebook_id,
                    workspace_id,
                    {k: literal(v) for k, v in bi_params.items()},
                    depends=["Run Complete SCHADS Audit"],
                ),
            ],
        }
    }


def canonical_file_pipeline(
    workspace_id,
    readiness_notebook_id,
    audit_notebook_id,
    bi_notebook_id,
    file_cfg,
    hist,
    bi_params,
):
    return {
        "properties": {
            "description": "Validate and audit canonical AuditHero CSV/XLSX files",
            "parameters": {
                "input_root": {
                    "type": "string",
                    "defaultValue": file_cfg.get("input_root", "/lakehouse/default/Files/input"),
                },
                "start_date": {
                    "type": "string",
                    "defaultValue": hist.get("start_date", "2023-07-01"),
                },
                "end_date": {
                    "type": "string",
                    "defaultValue": hist.get("end_date", "2026-06-30"),
                },
            },
            "activities": [
                notebook_activity(
                    "Validate Canonical Files",
                    readiness_notebook_id,
                    workspace_id,
                    {"input_root": expression("@pipeline().parameters.input_root")},
                ),
                notebook_activity(
                    "Audit Canonical Files",
                    audit_notebook_id,
                    workspace_id,
                    {
                        "input_root": expression("@pipeline().parameters.input_root"),
                        "start_date": expression("@pipeline().parameters.start_date"),
                        "end_date": expression("@pipeline().parameters.end_date"),
                        "run_type": literal("CANONICAL_FILE"),
                    },
                    depends=["Validate Canonical Files"],
                ),
                notebook_activity(
                    "Refresh Direct Lake and Power BI",
                    bi_notebook_id,
                    workspace_id,
                    {k: literal(v) for k, v in bi_params.items()},
                    depends=["Audit Canonical Files"],
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
    auto_cfg = cfg.get("auto_file_source", {})
    file_cfg = cfg.get("manual_file_source", {})
    hist = cfg.get("historical_defaults", {})
    client = FabricClient(ws, access_token())

    lakehouse = client.find("Lakehouse", cfg.get("lakehouse_name", "AuditHero_Lakehouse"))
    environment = client.find("Environment", cfg.get("environment_name", "AuditHero_Environment"))
    bi = client.find("Notebook", "AuditHero - Build BI")
    if not lakehouse or not environment or not bi:
        raise RuntimeError(
            "Run fabric/scripts/deploy_fabric.py first; Lakehouse, Environment or BI notebook is missing"
        )

    auto_source_root = auto_cfg.get("source_root", "/lakehouse/default/Files/import/raw")
    auto_output_root = auto_cfg.get("output_root", "/lakehouse/default/Files/auto_input")
    auto_code = (FABRIC / "notebooks" / "03e_auto_intake.py").read_text(encoding="utf-8")
    auto_notebook = client.upsert_notebook(
        "AuditHero - Auto Prepare Uploaded Files",
        auto_code,
        lakehouse,
        environment,
        {
            "source_root": auto_source_root,
            "output_root": auto_output_root,
            "start_date": "",
            "end_date": "",
        },
    )

    input_root = file_cfg.get("input_root", "/lakehouse/default/Files/input")
    readiness_code = (FABRIC / "notebooks" / "03b_file_readiness.py").read_text(encoding="utf-8")
    readiness = client.upsert_notebook(
        "AuditHero - Canonical Files Readiness",
        readiness_code,
        lakehouse,
        environment,
        {"input_root": input_root},
    )

    audit_code = (FABRIC / "notebooks" / "04b_manual_file_audit.py").read_text(encoding="utf-8")
    audit_notebook = client.upsert_notebook(
        "AuditHero - Audit Uploaded CSV Excel",
        audit_code,
        lakehouse,
        environment,
        {
            "input_root": auto_output_root,
            "start_date": "",
            "end_date": "",
            "run_type": "AUTO_FILE",
        },
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

    auto_pipeline_item = client.upsert_pipeline(
        auto_cfg.get("pipeline_name", "AuditHero - Auto Audit Uploaded Files"),
        auto_file_pipeline(
            ws,
            auto_notebook["id"],
            audit_notebook["id"],
            bi["id"],
            auto_cfg,
            bi_params,
        ),
    )

    canonical_pipeline_item = client.upsert_pipeline(
        file_cfg.get("pipeline_name", "AuditHero - Canonical Files Audit (Advanced)"),
        canonical_file_pipeline(
            ws,
            readiness["id"],
            audit_notebook["id"],
            bi["id"],
            file_cfg,
            hist,
            bi_params,
        ),
    )

    state_path = FABRIC / "deployment_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    state["auto_file_notebook_id"] = auto_notebook["id"]
    state["auto_file_pipeline_id"] = auto_pipeline_item["id"]
    state["manual_file_readiness_notebook_id"] = readiness["id"]
    state["manual_file_notebook_id"] = audit_notebook["id"]
    state["manual_file_pipeline_id"] = canonical_pipeline_item["id"]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print("AuditHero uploaded-file audit paths deployed")
    print(f"Primary pipeline: {auto_cfg.get('pipeline_name', 'AuditHero - Auto Audit Uploaded Files')}")
    print(f"Raw upload folder: {auto_source_root}")
    print(f"Advanced canonical pipeline: {file_cfg.get('pipeline_name', 'AuditHero - Canonical Files Audit (Advanced)')}")


if __name__ == "__main__":
    main()
