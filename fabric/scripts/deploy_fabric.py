#!/usr/bin/env python3
"""Deploy the complete AuditHero Microsoft Fabric application.

Creates/updates a schema-enabled Lakehouse, Runtime Environment, PySpark notebooks,
historical/monthly pipelines and a disabled monthly schedule. Setup/self-test/BI
are executed through Fabric item jobs after deployment.

Authentication order:
1. FABRIC_ACCESS_TOKEN environment variable
2. Azure CLI: az account get-access-token --resource https://api.fabric.microsoft.com
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

API = "https://api.fabric.microsoft.com/v1"
ROOT = Path(__file__).resolve().parents[2]
FABRIC = ROOT / "fabric"


def b64(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode("ascii")


def access_token() -> str:
    token = os.getenv("FABRIC_ACCESS_TOKEN")
    if token:
        return token
    try:
        return subprocess.check_output(
            [
                "az",
                "account",
                "get-access-token",
                "--resource",
                "https://api.fabric.microsoft.com",
                "--query",
                "accessToken",
                "-o",
                "tsv",
            ],
            text=True,
        ).strip()
    except Exception as exc:
        raise SystemExit(
            "No Fabric token available. Run 'az login' or set FABRIC_ACCESS_TOKEN."
        ) from exc


class FabricClient:
    def __init__(self, workspace_id: str, token: str):
        self.workspace_id = workspace_id
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{API}{path}"

    def request(self, method: str, path: str, *, body=None, ok=(200, 201, 202, 204), wait=True):
        url = self._url(path)
        for attempt in range(8):
            r = self.session.request(method, url, json=body, timeout=120)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", min(60, 2 ** attempt))))
                continue
            if r.status_code not in ok:
                raise RuntimeError(f"Fabric {method} {url} -> {r.status_code}: {r.text}")
            if r.status_code == 202 and wait:
                return self.wait_operation(r)
            if not r.content:
                return None
            try:
                return r.json()
            except ValueError:
                return r.text
        raise RuntimeError(f"Fabric request remained rate-limited: {method} {url}")

    def wait_operation(self, response):
        location = response.headers.get("Location")
        if not location:
            return None
        deadline = time.time() + 1800
        delay = max(2, int(response.headers.get("Retry-After", "5")))
        while time.time() < deadline:
            time.sleep(min(delay, 30))
            r = self.session.get(location, timeout=120)
            if r.status_code == 429:
                delay = int(r.headers.get("Retry-After", "10"))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Fabric LRO {location} -> {r.status_code}: {r.text}")
            if not r.content:
                if r.status_code in (200, 201, 204):
                    return None
                continue
            try:
                payload = r.json()
            except ValueError:
                if r.status_code in (200, 201, 204):
                    return r.text
                continue
            status = str(payload.get("status") or payload.get("state") or "").lower()
            if status in {"succeeded", "success", "completed"}:
                return payload
            if status in {"failed", "cancelled", "canceled"}:
                raise RuntimeError(f"Fabric operation failed: {json.dumps(payload)}")
            if r.status_code in (200, 201) and not status:
                return payload
        raise TimeoutError(f"Timed out waiting for Fabric operation: {location}")

    def items(self) -> list[dict]:
        path = f"/workspaces/{self.workspace_id}/items"
        result=[]
        while path:
            payload=self.request("GET", path)
            result.extend(payload.get("value", []))
            token=payload.get("continuationToken")
            path=(f"/workspaces/{self.workspace_id}/items?continuationToken={token}" if token else None)
        return result

    def find(self, item_type: str, name: str):
        for item in self.items():
            if item.get("type") == item_type and item.get("displayName") == name:
                return item
        return None

    def create_lakehouse(self, name: str):
        existing=self.find("Lakehouse", name)
        if existing:
            return existing
        self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/lakehouses",
            body={
                "displayName": name,
                "description": "AuditHero SCHADS payroll compliance Lakehouse",
                "creationPayload": {"enableSchemas": True},
            },
        )
        item=self.find("Lakehouse", name)
        if not item:
            raise RuntimeError("Lakehouse creation completed but item could not be resolved")
        return item

    def create_environment(self, name: str):
        existing=self.find("Environment", name)
        if existing:
            return existing
        self.request(
            "POST", f"/workspaces/{self.workspace_id}/environments",
            body={"displayName": name, "description": "AuditHero Fabric Runtime environment"},
        )
        item=self.find("Environment", name)
        if not item:
            raise RuntimeError("Environment creation completed but item could not be resolved")
        return item

    def update_environment(self, environment_id: str, environment_yml: bytes, spark_yml: bytes, wheel: bytes, wheel_name: str):
        parts=[
            {"path":"Libraries/PublicLibraries/environment.yml","payload":b64(environment_yml),"payloadType":"InlineBase64"},
            {"path":"Setting/Sparkcompute.yml","payload":b64(spark_yml),"payloadType":"InlineBase64"},
            {"path":f"Libraries/CustomLibraries/{wheel_name}","payload":b64(wheel),"payloadType":"InlineBase64"},
        ]
        self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/environments/{environment_id}/updateDefinition",
            body={"definition":{"parts":parts}},
        )
        # Current GA contract requires beta=false through 31 Aug 2026 transition.
        self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/environments/{environment_id}/staging/publish?beta=false",
            body=None,
        )

    @staticmethod
    def notebook_source(code: str, lakehouse: dict, environment: dict, workspace_id: str) -> str:
        # Strip an existing source header so redeploys are deterministic.
        if code.startswith("# Fabric notebook source"):
            marker="# CELL ********************"
            pos=code.find(marker)
            if pos >= 0:
                code=code[pos+len(marker):].lstrip("\n")
        meta={
            "kernel_info":{"name":"synapse_pyspark"},
            "dependencies":{
                "lakehouse":{
                    "default_lakehouse":lakehouse["id"],
                    "default_lakehouse_name":lakehouse["displayName"],
                    "default_lakehouse_workspace_id":workspace_id,
                    "known_lakehouses":[{"id":lakehouse["id"]}],
                },
                "environment":{
                    "environmentId":environment["id"],
                    "workspaceId":workspace_id,
                },
            },
        }
        meta_lines="\n".join(f"# META {line}" for line in json.dumps(meta,indent=2).splitlines())
        return (
            "# Fabric notebook source\n\n# METADATA ********************\n"
            + meta_lines
            + "\n\n# CELL ********************\n\n"
            + code.rstrip()
            + "\n\n# METADATA ********************\n"
            + "# META {\n# META   \"language\": \"python\",\n# META   \"language_group\": \"synapse_pyspark\"\n# META }\n"
        )

    def upsert_notebook(self, name: str, code: str, lakehouse: dict, environment: dict):
        source=self.notebook_source(code,lakehouse,environment,self.workspace_id)
        definition={"format":"fabricGitSource","parts":[{"path":"notebook-content.py","payload":b64(source),"payloadType":"InlineBase64"}]}
        existing=self.find("Notebook",name)
        if not existing:
            self.request(
                "POST",f"/workspaces/{self.workspace_id}/notebooks",
                body={"displayName":name,"description":"AuditHero managed notebook","definition":definition},
            )
            existing=self.find("Notebook",name)
        else:
            self.request(
                "POST",f"/workspaces/{self.workspace_id}/notebooks/{existing['id']}/updateDefinition?updateMetadata=true",
                body={"definition":definition},
            )
        if not existing:
            raise RuntimeError(f"Notebook could not be resolved after deployment: {name}")
        return existing

    def upsert_pipeline(self, name: str, content: dict):
        definition={"parts":[{"path":"pipeline-content.json","payload":b64(json.dumps(content,separators=(",",":"))),"payloadType":"InlineBase64"}]}
        existing=self.find("DataPipeline",name)
        if not existing:
            self.request(
                "POST",f"/workspaces/{self.workspace_id}/dataPipelines",
                body={"displayName":name,"description":"AuditHero managed pipeline","definition":definition},
            )
            existing=self.find("DataPipeline",name)
        else:
            self.request(
                "POST",f"/workspaces/{self.workspace_id}/dataPipelines/{existing['id']}/updateDefinition",
                body={"definition":definition},
            )
        if not existing:
            raise RuntimeError(f"Pipeline could not be resolved after deployment: {name}")
        return existing

    def run_job(self, item_id: str, job_type="RunNotebook", execution_data=None):
        path=f"/workspaces/{self.workspace_id}/items/{item_id}/jobs/instances?jobType={job_type}"
        body={} if execution_data is None else {"executionData":execution_data}
        return self.request("POST",path,body=body,ok=(200,201,202),wait=True)

    def ensure_monthly_schedule(self, pipeline_id: str, *, day: int, time_hhmm: str, timezone_id: str, enabled: bool):
        path=f"/workspaces/{self.workspace_id}/items/{pipeline_id}/jobs/DefaultJob/schedules"
        existing=self.request("GET",path).get("value",[])
        now=datetime.now(timezone.utc)+timedelta(minutes=5)
        end=now+timedelta(days=3650)
        body={
            "enabled":bool(enabled),
            "configuration":{
                "type":"Monthly",
                "startDateTime":now.replace(microsecond=0).isoformat().replace("+00:00","Z"),
                "endDateTime":end.replace(microsecond=0).isoformat().replace("+00:00","Z"),
                "localTimeZoneId":timezone_id,
                "recurrence":1,
                "times":[time_hhmm],
                "occurrence":{"occurrenceType":"DayOfMonth","dayOfMonth":int(day)},
            },
        }
        if existing:
            self.request("PATCH",f"{path}/{existing[0]['id']}",body=body)
            return existing[0]["id"]
        created=self.request("POST",path,body=body)
        return created.get("id") if isinstance(created,dict) else None


def expression(value: str) -> dict:
    return {"value":value,"type":"Expression"}


def literal(value: Any) -> dict:
    return {"value":value,"type":"String"}


def notebook_activity(name: str, notebook_id: str, workspace_id: str, parameters: dict, depends=None):
    return {
        "name":name,
        "type":"TridentNotebook",
        "dependsOn":[{"activity":d,"dependencyConditions":["Succeeded"]} for d in (depends or [])],
        "policy":{"timeout":"0.12:00:00","retry":1,"retryIntervalInSeconds":30,"secureInput":False,"secureOutput":False},
        "typeProperties":{"notebookId":notebook_id,"workspaceId":workspace_id,"parameters":parameters},
    }


def historical_pipeline(workspace_id: str, notebook_id: str, bi_notebook_id: str, cfg: dict):
    return {
        "properties":{
            "description":"Parameterised Employment Hero historical SCHADS audit",
            "parameters":{
                "start_date":{"type":"string","defaultValue":cfg.get("historical_default_start","2023-07-01")},
                "end_date":{"type":"string","defaultValue":cfg.get("historical_default_end","2026-06-30")},
                "actual_pay_source":{"type":"string","defaultValue":cfg.get("actual_pay_source","PAYROLL_API")},
            },
            "activities":[
                notebook_activity(
                    "Run Historical Audit",notebook_id,workspace_id,
                    {
                        "key_vault_url":literal(cfg["key_vault_url"]),
                        "start_date":expression("@pipeline().parameters.start_date"),
                        "end_date":expression("@pipeline().parameters.end_date"),
                        "actual_pay_source":expression("@pipeline().parameters.actual_pay_source"),
                    },
                ),
                notebook_activity("Refresh BI Snapshots",bi_notebook_id,workspace_id,{},depends=["Run Historical Audit"]),
            ],
        }
    }


def monthly_pipeline(workspace_id: str, notebook_id: str, bi_notebook_id: str, cfg: dict):
    return {
        "properties":{
            "description":"Recurring AuditHero payroll compliance audit",
            "activities":[
                notebook_activity(
                    "Run Monthly Audit",notebook_id,workspace_id,
                    {
                        "key_vault_url":literal(cfg["key_vault_url"]),
                        "lookback_days":literal(str(cfg.get("monthly_lookback_days",45))),
                        "actual_pay_source":literal(cfg.get("actual_pay_source","PAYROLL_API")),
                    },
                ),
                notebook_activity("Refresh BI Snapshots",bi_notebook_id,workspace_id,{},depends=["Run Monthly Audit"]),
            ],
        }
    }


def build_wheel(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True,exist_ok=True)
    script=FABRIC/"scripts"/"build_fabric_wheel.py"
    if script.exists():
        subprocess.check_call([sys.executable,str(script),"--output-dir",str(output_dir)],cwd=ROOT)
        wheels=sorted(output_dir.glob("*.whl"),key=lambda p:p.stat().st_mtime,reverse=True)
        if wheels:
            return wheels[0]
    # Fallback to standard build. Package-data configuration must include bundled rules.
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","build"],cwd=ROOT)
    subprocess.check_call([sys.executable,"-m","build","--wheel","--outdir",str(output_dir)],cwd=ROOT)
    wheels=sorted(output_dir.glob("*.whl"),key=lambda p:p.stat().st_mtime,reverse=True)
    if not wheels:
        raise RuntimeError("AuditHero wheel build produced no .whl")
    return wheels[0]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",default=str(FABRIC/"config"/"fabric.json"))
    ap.add_argument("--skip-run",action="store_true",help="Deploy definitions but do not execute setup/self-test/BI")
    args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text(encoding="utf-8"))
    ws=cfg["workspace_id"]
    client=FabricClient(ws,access_token())

    print("[1/8] Lakehouse")
    lakehouse=client.create_lakehouse(cfg.get("lakehouse_name","AuditHero_Lakehouse"))

    print("[2/8] Build + publish Runtime Environment")
    environment=client.create_environment(cfg.get("environment_name","AuditHero_Environment"))
    wheel=build_wheel(ROOT/"dist"/"fabric")
    env_yml=(FABRIC/"environment"/"environment.yml").read_bytes()
    spark_yml=(FABRIC/"environment"/"Sparkcompute.yml").read_bytes()
    client.update_environment(environment["id"],env_yml,spark_yml,wheel.read_bytes(),wheel.name)

    print("[3/8] Notebooks")
    notebook_files={
        "AuditHero - Setup":"00_setup.py",
        "AuditHero - Self Test":"01_self_test.py",
        "AuditHero - Employment Hero Connection":"02_connection_test.py",
        "AuditHero - Readiness":"03_readiness.py",
        "AuditHero - Historical Audit":"04_historical_audit.py",
        "AuditHero - Monthly Audit":"05_monthly_audit.py",
        "AuditHero - Build BI":"06_build_bi.py",
    }
    notebooks={}
    for name,file_name in notebook_files.items():
        code=(FABRIC/"notebooks"/file_name).read_text(encoding="utf-8")
        notebooks[name]=client.upsert_notebook(name,code,lakehouse,environment)

    print("[4/8] Pipelines")
    historical=client.upsert_pipeline(
        cfg.get("historical_pipeline_name","AuditHero - Historical Audit Pipeline"),
        historical_pipeline(ws,notebooks["AuditHero - Historical Audit"]["id"],notebooks["AuditHero - Build BI"]["id"],cfg),
    )
    monthly=client.upsert_pipeline(
        cfg.get("monthly_pipeline_name","AuditHero - Monthly Payroll Pipeline"),
        monthly_pipeline(ws,notebooks["AuditHero - Monthly Audit"]["id"],notebooks["AuditHero - Build BI"]["id"],cfg),
    )

    print("[5/8] Monthly schedule")
    client.ensure_monthly_schedule(
        monthly["id"],
        day=int(cfg.get("monthly_day",25)),
        time_hhmm=cfg.get("monthly_time","09:00"),
        timezone_id=cfg.get("windows_timezone","W. Australia Standard Time"),
        enabled=bool(cfg.get("monthly_schedule_enabled",False)),
    )

    if not args.skip_run:
        print("[6/8] Setup")
        client.run_job(notebooks["AuditHero - Setup"]["id"])
        print("[7/8] Runtime self-test")
        client.run_job(notebooks["AuditHero - Self Test"]["id"])
        print("[8/8] Direct Lake semantic model + Power BI")
        client.run_job(notebooks["AuditHero - Build BI"]["id"])
    else:
        print("[6-8/8] Execution skipped by --skip-run")

    state={
        "workspace_id":ws,
        "lakehouse_id":lakehouse["id"],
        "environment_id":environment["id"],
        "historical_pipeline_id":historical["id"],
        "monthly_pipeline_id":monthly["id"],
        "notebooks":{k:v["id"] for k,v in notebooks.items()},
        "monthly_schedule_enabled":bool(cfg.get("monthly_schedule_enabled",False)),
    }
    out=FABRIC/"deployment_state.json"
    out.write_text(json.dumps(state,indent=2),encoding="utf-8")
    print("\nAuditHero Fabric deployment complete")
    print(json.dumps(state,indent=2))
    print("NEXT: add Key Vault secrets, run connection/readiness, validate one known pay period, then enable monthly schedule.")


if __name__ == "__main__":
    main()
