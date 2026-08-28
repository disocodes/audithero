#!/usr/bin/env python3
"""Canonical complete AuditHero Fabric installer.

Builds FabricGitSource notebooks with real parameter cells, binds them to the
AuditHero Lakehouse and Environment, and uses the current notebook Job Scheduler
API for unattended execution.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import deploy_fabric as base


class FabricClient(base.FabricClient):
    def resolve_item(self, item_type: str, name: str, attempts: int = 20):
        for _ in range(attempts):
            item = self.find(item_type, name)
            if item:
                return item
            time.sleep(2)
        return None

    @staticmethod
    def notebook_source(code, lakehouse, environment, workspace_id, parameters=None):
        """Generate valid FabricGitSource, including a designated parameter cell."""
        meta = {
            "kernel_info": {"name": "synapse_pyspark"},
            "dependencies": {
                "lakehouse": {
                    "default_lakehouse": lakehouse["id"],
                    "default_lakehouse_name": lakehouse["displayName"],
                    "default_lakehouse_workspace_id": workspace_id,
                    "known_lakehouses": [{"id": lakehouse["id"]}],
                },
                "environment": {
                    "environmentId": environment["id"],
                    "workspaceId": workspace_id,
                },
            },
        }
        meta_lines = "\n".join(
            f"# META {line}" for line in json.dumps(meta, indent=2).splitlines()
        )
        cell_meta = (
            "# METADATA ********************\n"
            "# META {\n"
            "# META   \"language\": \"python\",\n"
            "# META   \"language_group\": \"synapse_pyspark\"\n"
            "# META }\n"
        )
        parts = [
            "# Fabric notebook source\n\n# METADATA ********************\n",
            meta_lines,
            "\n\n",
        ]
        parameters = parameters or {}
        if parameters:
            parts.append("# PARAMETERS CELL ********************\n\n")
            for key, value in parameters.items():
                parts.append(f"{key} = {repr(value)}\n")
            parts.append("\n" + cell_meta + "\n")
        parts.append("# CELL ********************\n\n")
        parts.append(code.strip() + "\n\n")
        parts.append(cell_meta)
        return "".join(parts)

    def upsert_notebook(self, name, code, lakehouse, environment, parameters=None):
        source = self.notebook_source(
            code, lakehouse, environment, self.workspace_id, parameters=parameters
        )
        definition = {
            "format": "fabricGitSource",
            "parts": [
                {
                    "path": "notebook-content.py",
                    "payload": base.b64(source),
                    "payloadType": "InlineBase64",
                }
            ],
        }
        existing = self.find("Notebook", name)
        if not existing:
            self.request(
                "POST",
                f"/workspaces/{self.workspace_id}/notebooks",
                body={
                    "displayName": name,
                    "description": "AuditHero managed notebook",
                    "definition": definition,
                },
            )
            existing = self.resolve_item("Notebook", name)
        else:
            self.request(
                "POST",
                f"/workspaces/{self.workspace_id}/notebooks/{existing['id']}/updateDefinition?updateMetadata=true",
                body={"definition": definition},
            )
        if not existing:
            raise RuntimeError(f"Notebook could not be resolved after deployment: {name}")
        return existing

    def run_notebook(self, item_id: str, parameters=None):
        """Execute a Fabric notebook through the GA notebook Job Scheduler API."""
        body = {}
        if parameters:
            body["parameters"] = [
                {"name": name, "value": value, "type": "Automatic"}
                for name, value in parameters.items()
            ]
        return self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/notebooks/{item_id}/jobs/execute/instances?beta=false",
            body=body,
            ok=(200, 201, 202),
            wait=True,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "fabric" / "config" / "fabric.json"))
    ap.add_argument("--skip-run", action="store_true")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    ws = cfg["workspace_id"]
    client = FabricClient(ws, base.access_token())

    print("[1/8] Create/update schema-enabled Lakehouse")
    lakehouse = client.create_lakehouse(cfg.get("lakehouse_name", "AuditHero_Lakehouse"))

    print("[2/8] Create/update/publish Runtime 2.0 Environment")
    environment = client.create_environment(
        cfg.get("environment_name", "AuditHero_Environment")
    )
    wheel = base.build_wheel(ROOT / "dist" / "fabric")
    env_yml = (ROOT / "fabric" / "environment" / "environment.yml").read_bytes()
    runtime_ref = ROOT / "fabric" / "environment" / "runtime-2.0.reference.yml"
    spark_path = (
        runtime_ref
        if runtime_ref.exists()
        else ROOT / "fabric" / "environment" / "Sparkcompute.yml"
    )
    client.update_environment(
        environment["id"], env_yml, spark_path.read_bytes(), wheel.read_bytes(), wheel.name
    )

    print("[3/8] Create/update bound, parameterized Fabric notebooks")
    common = {
        "key_vault_url": cfg["key_vault_url"],
        "actual_pay_source": cfg.get("actual_pay_source", "PAYROLL_API"),
    }
    notebook_specs = {
        "AuditHero - Setup": ("00_setup.py", {}),
        "AuditHero - Self Test": ("01_self_test.py", {}),
        "AuditHero - Employment Hero Connection": (
            "02_connection_test.py",
            {"key_vault_url": cfg["key_vault_url"]},
        ),
        "AuditHero - Readiness": (
            "03_readiness.py",
            {"key_vault_url": cfg["key_vault_url"]},
        ),
        "AuditHero - Historical Audit": (
            "04_historical_audit.py",
            {
                **common,
                "start_date": cfg.get("historical_default_start", "2023-07-01"),
                "end_date": cfg.get("historical_default_end", "2026-06-30"),
            },
        ),
        "AuditHero - Monthly Audit": (
            "05_monthly_audit.py",
            {
                **common,
                "lookback_days": int(cfg.get("monthly_lookback_days", 45)),
            },
        ),
        "AuditHero - Build BI": (
            "06_build_bi.py",
            {
                "workspace_name": ws,
                "lakehouse_name": cfg.get("lakehouse_name", "AuditHero_Lakehouse"),
                "semantic_model_name": cfg.get(
                    "semantic_model_name", "AuditHero - SCHADS Payroll Compliance"
                ),
                "report_name": cfg.get(
                    "report_name", "AuditHero - SCHADS Payroll Compliance"
                ),
            },
        ),
    }
    notebooks = {}
    for name, (file_name, parameters) in notebook_specs.items():
        code = (ROOT / "fabric" / "notebooks" / file_name).read_text(encoding="utf-8")
        notebooks[name] = client.upsert_notebook(
            name, code, lakehouse, environment, parameters=parameters
        )

    print("[4/8] Create/update Data Factory pipelines")
    historical = client.upsert_pipeline(
        cfg.get("historical_pipeline_name", "AuditHero - Historical Audit Pipeline"),
        base.historical_pipeline(
            ws,
            notebooks["AuditHero - Historical Audit"]["id"],
            notebooks["AuditHero - Build BI"]["id"],
            cfg,
        ),
    )
    monthly = client.upsert_pipeline(
        cfg.get("monthly_pipeline_name", "AuditHero - Monthly Payroll Pipeline"),
        base.monthly_pipeline(
            ws,
            notebooks["AuditHero - Monthly Audit"]["id"],
            notebooks["AuditHero - Build BI"]["id"],
            cfg,
        ),
    )

    print("[5/8] Create/update monthly schedule")
    client.ensure_monthly_schedule(
        monthly["id"],
        day=int(cfg.get("monthly_day", 25)),
        time_hhmm=cfg.get("monthly_time", "09:00"),
        timezone_id=cfg.get("windows_timezone", "W. Australia Standard Time"),
        enabled=bool(cfg.get("monthly_schedule_enabled", False)),
    )

    if not args.skip_run:
        print("[6/8] Execute setup")
        client.run_notebook(notebooks["AuditHero - Setup"]["id"])
        print("[7/8] Execute Fabric-native regression self-test")
        client.run_notebook(notebooks["AuditHero - Self Test"]["id"])
        print("[8/8] Build/refresh Direct Lake semantic model and Power BI report")
        client.run_notebook(
            notebooks["AuditHero - Build BI"]["id"],
            parameters=notebook_specs["AuditHero - Build BI"][1],
        )
    else:
        print("[6-8/8] Runtime execution skipped")

    state = {
        "workspace_id": ws,
        "lakehouse_id": lakehouse["id"],
        "environment_id": environment["id"],
        "historical_pipeline_id": historical["id"],
        "monthly_pipeline_id": monthly["id"],
        "notebooks": {k: v["id"] for k, v in notebooks.items()},
        "monthly_schedule_enabled": bool(cfg.get("monthly_schedule_enabled", False)),
    }
    (ROOT / "fabric" / "deployment_state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    print("\nAuditHero Fabric COMPLETE deployment succeeded")
    print(json.dumps(state, indent=2))
    print(
        "NEXT: Key Vault secrets -> connection test -> readiness -> one known pay period "
        "-> historical audit -> enable monthly schedule."
    )


if __name__ == "__main__":
    main()
