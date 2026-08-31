#!/usr/bin/env python3
"""Deploy AuditHero's UI-facing source mapping and conversion pipelines to Fabric."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(FABRIC / "config" / "fabric.json"))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    ws = cfg["workspace_id"]
    source_cfg = cfg.get("source_mapping", {})
    defaults = {
        "source_root": source_cfg.get("source_root", "/lakehouse/default/Files/import/raw"),
        "draft_path": source_cfg.get("draft_path", "/lakehouse/default/Files/import/source_mapping_draft.xlsx"),
        "mapping_path": source_cfg.get("mapping_path", "/lakehouse/default/Files/import/source_mapping.xlsx"),
        "output_root": source_cfg.get("output_root", "/lakehouse/default/Files/input"),
    }

    client = FabricClient(ws, access_token())
    lakehouse = client.find("Lakehouse", cfg.get("lakehouse_name", "AuditHero_Lakehouse"))
    environment = client.find("Environment", cfg.get("environment_name", "AuditHero_Environment"))
    if not lakehouse or not environment:
        raise RuntimeError("AuditHero Lakehouse/Environment not found. Complete the base Fabric installation first.")

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

    draft_item = client.upsert_pipeline(
        source_cfg.get("draft_pipeline_name", "AuditHero - Build Source Mapping Workbook"),
        draft_pipeline(ws, draft_notebook["id"], defaults),
    )
    convert_item = client.upsert_pipeline(
        source_cfg.get("conversion_pipeline_name", "AuditHero - Convert Source Files"),
        conversion_pipeline(ws, convert_notebook["id"], defaults),
    )

    state_path = FABRIC / "deployment_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    state.update(
        {
            "source_mapping_draft_notebook_id": draft_notebook["id"],
            "source_mapping_convert_notebook_id": convert_notebook["id"],
            "source_mapping_draft_pipeline_id": draft_item["id"],
            "source_mapping_conversion_pipeline_id": convert_item["id"],
        }
    )
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print("AuditHero source-mapping pipelines deployed.")
    print("1. Upload raw exports under:", defaults["source_root"])
    print("2. Run 'AuditHero - Build Source Mapping Workbook'.")
    print("3. Edit/upload the approved mapping as:", defaults["mapping_path"])
    print("4. Run 'AuditHero - Convert Source Files'.")


if __name__ == "__main__":
    main()
