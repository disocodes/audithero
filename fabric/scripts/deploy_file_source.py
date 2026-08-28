#!/usr/bin/env python3
"""Add/update the credential-free CSV/XLSX audit path in Microsoft Fabric."""
from __future__ import annotations
import argparse, json
from pathlib import Path

from deploy_fabric import FabricClient, access_token, notebook_activity, literal, expression

ROOT=Path(__file__).resolve().parents[2]
FABRIC=ROOT/"fabric"


def file_pipeline(workspace_id, readiness_notebook_id, audit_notebook_id, bi_notebook_id, file_cfg, hist, bi_params):
    return {
        "properties":{
            "description":"Validate and audit uploaded AuditHero CSV/XLSX files without Employment Hero credentials",
            "parameters":{
                "input_root":{"type":"string","defaultValue":file_cfg.get("input_root","/lakehouse/default/Files/input")},
                "start_date":{"type":"string","defaultValue":hist.get("start_date","2023-07-01")},
                "end_date":{"type":"string","defaultValue":hist.get("end_date","2026-06-30")},
            },
            "activities":[
                notebook_activity(
                    "Validate Uploaded Files",readiness_notebook_id,workspace_id,
                    {"input_root":expression("@pipeline().parameters.input_root")},
                ),
                notebook_activity(
                    "Audit Uploaded Files",audit_notebook_id,workspace_id,
                    {
                        "input_root":expression("@pipeline().parameters.input_root"),
                        "start_date":expression("@pipeline().parameters.start_date"),
                        "end_date":expression("@pipeline().parameters.end_date"),
                    },depends=["Validate Uploaded Files"],
                ),
                notebook_activity(
                    "Refresh Direct Lake and Power BI",bi_notebook_id,workspace_id,
                    {k:literal(v) for k,v in bi_params.items()},depends=["Audit Uploaded Files"],
                ),
            ],
        }
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",default=str(FABRIC/"config"/"fabric.json")); args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text(encoding="utf-8")); ws=cfg["workspace_id"]
    file_cfg=cfg.get("manual_file_source",{}); hist=cfg.get("historical_defaults",{})
    client=FabricClient(ws,access_token())
    lakehouse=client.find("Lakehouse",cfg.get("lakehouse_name","AuditHero_Lakehouse"))
    environment=client.find("Environment",cfg.get("environment_name","AuditHero_Environment"))
    bi=client.find("Notebook","AuditHero - Build BI")
    if not lakehouse or not environment or not bi:
        raise RuntimeError("Run fabric/scripts/deploy_fabric.py first; Lakehouse, Environment or BI notebook is missing")

    input_root=file_cfg.get("input_root","/lakehouse/default/Files/input")
    readiness_code=(FABRIC/"notebooks"/"03b_file_readiness.py").read_text(encoding="utf-8")
    readiness=client.upsert_notebook("AuditHero - Uploaded Files Readiness",readiness_code,lakehouse,environment,{"input_root":input_root})

    audit_params={"input_root":input_root,"start_date":hist.get("start_date","2023-07-01"),"end_date":hist.get("end_date","2026-06-30")}
    code=(FABRIC/"notebooks"/"04b_manual_file_audit.py").read_text(encoding="utf-8")
    notebook=client.upsert_notebook("AuditHero - Audit Uploaded CSV Excel",code,lakehouse,environment,audit_params)

    workspace_name=cfg.get("workspace_name") or ws; lakehouse_name=cfg.get("lakehouse_name","AuditHero_Lakehouse")
    semantic_model_name=cfg.get("semantic_model_name","AuditHero - SCHADS Payroll Compliance")
    bi_params={"workspace_name":workspace_name,"lakehouse_name":lakehouse_name,"semantic_model_name":semantic_model_name,"report_name":cfg.get("report_name",semantic_model_name)}
    pipeline=client.upsert_pipeline(
        file_cfg.get("pipeline_name","AuditHero - Uploaded Files Audit Pipeline"),
        file_pipeline(ws,readiness["id"],notebook["id"],bi["id"],file_cfg,hist,bi_params),
    )

    state_path=FABRIC/"deployment_state.json"
    state=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    state["manual_file_readiness_notebook_id"]=readiness["id"]
    state["manual_file_notebook_id"]=notebook["id"]
    state["manual_file_pipeline_id"]=pipeline["id"]
    state_path.write_text(json.dumps(state,indent=2),encoding="utf-8")
    print("Credential-free CSV/XLSX Fabric audit path deployed")
    print(f"Pipeline: {file_cfg.get('pipeline_name','AuditHero - Uploaded Files Audit Pipeline')}")
    print(f"Default input folder: {input_root}")

if __name__=="__main__": main()
