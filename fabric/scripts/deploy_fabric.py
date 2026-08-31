#!/usr/bin/env python3
"""Deploy the complete AuditHero Microsoft Fabric application.

Creates/updates:
- schema-enabled Lakehouse
- Runtime 2.0 Environment with AuditHero wheel
- bound/parameterized Fabric notebooks
- historical and monthly Data Factory pipelines
- disabled-by-default monthly schedule
- Direct Lake semantic model and Power BI report

Authentication order:
1. FABRIC_ACCESS_TOKEN
2. Azure CLI token for https://api.fabric.microsoft.com
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
                "az", "account", "get-access-token",
                "--resource", "https://api.fabric.microsoft.com",
                "--query", "accessToken", "-o", "tsv",
            ],
            text=True,
        ).strip()
    except Exception as exc:
        raise SystemExit(
            "No Fabric token available. Run 'az login' or set FABRIC_ACCESS_TOKEN."
        ) from exc


def _parameter_type(value: Any) -> str:
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "Number"
    return "Text"


def _fabric_literal(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    return repr(value)


class FabricClient:
    def __init__(self, workspace_id: str, token: str):
        self.workspace_id = workspace_id
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{API}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        body=None,
        ok=(200, 201, 202, 204),
        wait=True,
    ):
        url = self._url(path)
        for attempt in range(8):
            r = self.session.request(method, url, json=body, timeout=120)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", min(60, 2**attempt))))
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
                raise RuntimeError(f"Fabric operation {location} -> {r.status_code}: {r.text}")
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
        result: list[dict] = []
        while path:
            payload = self.request("GET", path)
            result.extend(payload.get("value", []))
            token = payload.get("continuationToken")
            path = (
                f"/workspaces/{self.workspace_id}/items?continuationToken={token}"
                if token
                else None
            )
        return result

    def find(self, item_type: str, name: str):
        for item in self.items():
            if item.get("type") == item_type and item.get("displayName") == name:
                return item
        return None

    def create_lakehouse(self, name: str):
        existing = self.find("Lakehouse", name)
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
        item = self.find("Lakehouse", name)
        if not item:
            raise RuntimeError("Lakehouse creation completed but item could not be resolved")
        return item

    def create_environment(self, name: str):
        existing = self.find("Environment", name)
        if existing:
            return existing
        self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/environments",
            body={
                "displayName": name,
                "description": "AuditHero Fabric Runtime environment",
            },
        )
        item = self.find("Environment", name)
        if not item:
            raise RuntimeError("Environment creation completed but item could not be resolved")
        return item

    @staticmethod
    def _publish_details(payload: Any) -> dict:
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("publishDetails"), dict):
            return payload["publishDetails"]
        properties = payload.get("properties")
        if isinstance(properties, dict) and isinstance(properties.get("publishDetails"), dict):
            return properties["publishDetails"]
        return {}

    def wait_environment_publish(self, environment_id: str, initial: Any = None):
        """Wait until Fabric confirms that staged libraries/runtime are active."""
        payload = initial if isinstance(initial, dict) else {}
        deadline = time.time() + 1800
        last_state = None

        while time.time() < deadline:
            details = self._publish_details(payload)
            state = str(details.get("state") or "").strip().lower()

            if state and state != last_state:
                print(f"    Environment publish state: {details.get('state')}", flush=True)
                last_state = state

            if state == "success":
                return details
            if state in {"failed", "cancelled", "canceled"}:
                raise RuntimeError(
                    "Fabric Environment publish failed: "
                    + json.dumps(details or payload, default=str)
                )

            time.sleep(10)
            payload = self.request(
                "GET",
                f"/workspaces/{self.workspace_id}/environments/{environment_id}",
                wait=False,
            )

        raise TimeoutError(
            f"Timed out waiting for Fabric Environment {environment_id} to publish"
        )

    def update_environment(
        self,
        environment_id: str,
        environment_yml: bytes,
        spark_yml: bytes,
        wheel: bytes,
        wheel_name: str,
    ):
        parts = [
            {
                "path": "Libraries/PublicLibraries/environment.yml",
                "payload": b64(environment_yml),
                "payloadType": "InlineBase64",
            },
            {
                "path": "Setting/Sparkcompute.yml",
                "payload": b64(spark_yml),
                "payloadType": "InlineBase64",
            },
            {
                "path": f"Libraries/CustomLibraries/{wheel_name}",
                "payload": b64(wheel),
                "payloadType": "InlineBase64",
            },
        ]
        self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/environments/{environment_id}/updateDefinition",
            body={"definition": {"parts": parts}},
        )
        # Fabric can return HTTP 200 while publishDetails.state is still Running.
        # Never launch AuditHero notebooks until the wheel/runtime publish is Success.
        publish = self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/environments/{environment_id}/staging/publish?beta=false",
            body=None,
        )
        self.wait_environment_publish(environment_id, publish)

    @staticmethod
    def notebook_source(
        code: str,
        lakehouse: dict,
        environment: dict,
        workspace_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """Create a FabricGitSource PySpark notebook with a real parameter cell."""
        if code.startswith("# Fabric notebook source"):
            marker = "# CELL ********************"
            pos = code.find(marker)
            if pos >= 0:
                code = code[pos + len(marker):].lstrip("\n")

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
        chunks = [
            "# Fabric notebook source",
            "",
            "# METADATA ********************",
            meta_lines,
        ]

        if parameters:
            chunks.extend(
                [
                    "",
                    "# CELL ********************",
                    "",
                    *[f"{name} = {_fabric_literal(value)}" for name, value in parameters.items()],
                    "",
                    "# METADATA ********************",
                    "# META {",
                    '# META   "tags": [',
                    '# META     "parameters"',
                    "# META   ],",
                    '# META   "language": "python",',
                    '# META   "language_group": "synapse_pyspark"',
                    "# META }",
                ]
            )

        chunks.extend(
            [
                "",
                "# CELL ********************",
                "",
                code.rstrip(),
                "",
                "# METADATA ********************",
                "# META {",
                '# META   "language": "python",',
                '# META   "language_group": "synapse_pyspark"',
                "# META }",
                "",
            ]
        )
        return "\n".join(chunks)

    def upsert_notebook(
        self,
        name: str,
        code: str,
        lakehouse: dict,
        environment: dict,
        parameters: dict[str, Any] | None = None,
    ):
        source = self.notebook_source(
            code, lakehouse, environment, self.workspace_id, parameters
        )
        definition = {
            "format": "fabricGitSource",
            "parts": [
                {
                    "path": "notebook-content.py",
                    "payload": b64(source),
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
            existing = self.find("Notebook", name)
        else:
            # updateMetadata=true requires a .platform definition part. AuditHero
            # only replaces source/bindings, so preserve the Fabric item metadata.
            self.request(
                "POST",
                f"/workspaces/{self.workspace_id}/notebooks/{existing['id']}/updateDefinition",
                body={"definition": definition},
            )
        if not existing:
            raise RuntimeError(f"Notebook could not be resolved after deployment: {name}")
        return existing

    def upsert_pipeline(self, name: str, content: dict):
        definition = {
            "parts": [
                {
                    "path": "pipeline-content.json",
                    "payload": b64(json.dumps(content, separators=(",", ":"))),
                    "payloadType": "InlineBase64",
                }
            ]
        }
        existing = self.find("DataPipeline", name)
        if not existing:
            self.request(
                "POST",
                f"/workspaces/{self.workspace_id}/dataPipelines",
                body={
                    "displayName": name,
                    "description": "AuditHero managed pipeline",
                    "definition": definition,
                },
            )
            existing = self.find("DataPipeline", name)
        else:
            self.request(
                "POST",
                f"/workspaces/{self.workspace_id}/dataPipelines/{existing['id']}/updateDefinition",
                body={"definition": definition},
            )
        if not existing:
            raise RuntimeError(f"Pipeline could not be resolved after deployment: {name}")
        return existing

    @staticmethod
    def _monitoring_links(payload: dict) -> dict:
        properties = payload.get("properties") if isinstance(payload, dict) else {}
        if not isinstance(properties, dict):
            properties = {}
        compute_details = properties.get("computeDetails")
        if not isinstance(compute_details, dict):
            compute_details = {}
        monitoring = compute_details.get("monitoringInfo")
        if not isinstance(monitoring, dict):
            monitoring = {}
        keys = (
            "executionSnapshotUrl",
            "driverLogUrl",
            "sparkJobDetailsUrl",
            "sparkUiUrl",
        )
        return {key: monitoring[key] for key in keys if monitoring.get(key)}

    def run_notebook(
        self,
        item_id: str,
        parameters: dict[str, Any] | None = None,
        *,
        lakehouse_id: str,
        environment_id: str,
    ):
        """Execute a Spark notebook with explicit compute bindings and rich diagnostics."""
        body = {
            "executionData": {
                "compute": "Spark",
                "computeConfiguration": {
                    "defaultLakehouse": {
                        "referenceType": "ById",
                        "itemId": lakehouse_id,
                        "workspaceId": self.workspace_id,
                    },
                    "attachedEnvironment": {
                        "referenceType": "ById",
                        "itemId": environment_id,
                        "workspaceId": self.workspace_id,
                    },
                },
            }
        }
        if parameters:
            body["parameters"] = [
                {"name": name, "value": value, "type": _parameter_type(value)}
                for name, value in parameters.items()
            ]

        url = self._url(
            f"/workspaces/{self.workspace_id}/notebooks/{item_id}"
            "/jobs/execute/instances?beta=false"
        )
        r = self.session.post(url, json=body, timeout=120)
        if r.status_code != 202:
            raise RuntimeError(f"Fabric POST {url} -> {r.status_code}: {r.text}")

        location = r.headers.get("Location", "")
        job_id = location.rstrip("/").split("/")[-1] if location else ""
        if not job_id:
            raise RuntimeError(
                "Fabric accepted the notebook run but returned no job instance Location"
            )

        poll_path = (
            f"/workspaces/{self.workspace_id}/notebooks/{item_id}"
            f"/jobs/execute/instances/{job_id}?beta=true"
        )
        deadline = time.time() + 1800
        delay = max(2, int(r.headers.get("Retry-After", "10")))

        while time.time() < deadline:
            time.sleep(min(delay, 30))
            payload = self.request("GET", poll_path, wait=False)
            if not isinstance(payload, dict):
                continue

            status = str(payload.get("status") or "").strip().lower()
            if status in {"completed", "succeeded", "success"}:
                failure = payload.get("failureReason")
                if failure:
                    links = self._monitoring_links(payload)
                    raise RuntimeError(
                        "Fabric notebook completed with a failure reason: "
                        + json.dumps(
                            {"job": payload, "monitoring": links},
                            default=str,
                        )
                    )
                return payload

            if status in {"failed", "cancelled", "canceled"}:
                links = self._monitoring_links(payload)
                details = {
                    "jobInstanceId": job_id,
                    "failureReason": payload.get("failureReason"),
                    "monitoring": links,
                    "rootActivityId": payload.get("rootActivityId"),
                }
                raise RuntimeError(
                    "Fabric notebook execution failed: "
                    + json.dumps(details, default=str)
                )

        raise TimeoutError(
            f"Timed out waiting for Fabric notebook {item_id} job {job_id}"
        )

    def ensure_monthly_schedule(
        self,
        pipeline_id: str,
        *,
        day: int,
        time_hhmm: str,
        timezone_id: str,
        enabled: bool,
    ):
        # Data Pipelines use the workload-specific execute scheduler endpoint.
        path = (
            f"/workspaces/{self.workspace_id}/dataPipelines/{pipeline_id}"
            "/jobs/execute/schedules"
        )
        existing = self.request("GET", path).get("value", [])
        now = datetime.now(timezone.utc) + timedelta(minutes=5)
        end = now + timedelta(days=3650)
        body = {
            "enabled": bool(enabled),
            "configuration": {
                "type": "Monthly",
                "startDateTime": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "endDateTime": end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "localTimeZoneId": timezone_id,
                "recurrence": 1,
                "times": [time_hhmm],
                "occurrence": {
                    "occurrenceType": "DayOfMonth",
                    "dayOfMonth": int(day),
                },
            },
        }
        if existing:
            self.request("PATCH", f"{path}/{existing[0]['id']}", body=body)
            return existing[0]["id"]
        created = self.request("POST", path, body=body)
        return created.get("id") if isinstance(created, dict) else None


def expression(value: str) -> dict:
    return {"value": value, "type": "Expression"}


def literal(value: Any) -> dict:
    return {"value": value, "type": "String"}


def notebook_activity(
    name: str,
    notebook_id: str,
    workspace_id: str,
    parameters: dict,
    depends=None,
):
    return {
        "name": name,
        "type": "TridentNotebook",
        "dependsOn": [
            {"activity": d, "dependencyConditions": ["Succeeded"]}
            for d in (depends or [])
        ],
        "policy": {
            "timeout": "0.12:00:00",
            "retry": 1,
            "retryIntervalInSeconds": 30,
            "secureInput": False,
            "secureOutput": False,
        },
        "typeProperties": {
            "notebookId": notebook_id,
            "workspaceId": workspace_id,
            "parameters": parameters,
        },
    }


def historical_pipeline(
    workspace_id: str,
    notebook_id: str,
    bi_notebook_id: str,
    cfg: dict,
    hist: dict,
    bi_params: dict,
):
    actual_source = hist.get("actual_pay_source", "PAYROLL_API")
    return {
        "properties": {
            "description": "Parameterised Employment Hero historical SCHADS audit",
            "parameters": {
                "start_date": {
                    "type": "string",
                    "defaultValue": hist.get("start_date", "2023-07-01"),
                },
                "end_date": {
                    "type": "string",
                    "defaultValue": hist.get("end_date", "2026-06-30"),
                },
                "actual_pay_source": {
                    "type": "string",
                    "defaultValue": actual_source,
                },
            },
            "activities": [
                notebook_activity(
                    "Run Historical Audit",
                    notebook_id,
                    workspace_id,
                    {
                        "key_vault_url": literal(cfg["key_vault_url"]),
                        "start_date": expression("@pipeline().parameters.start_date"),
                        "end_date": expression("@pipeline().parameters.end_date"),
                        "actual_pay_source": expression(
                            "@pipeline().parameters.actual_pay_source"
                        ),
                    },
                ),
                notebook_activity(
                    "Refresh Direct Lake and Power BI",
                    bi_notebook_id,
                    workspace_id,
                    {k: literal(v) for k, v in bi_params.items()},
                    depends=["Run Historical Audit"],
                ),
            ],
        }
    }


def monthly_pipeline(
    workspace_id: str,
    notebook_id: str,
    bi_notebook_id: str,
    cfg: dict,
    monthly: dict,
    hist: dict,
    bi_params: dict,
):
    return {
        "properties": {
            "description": "Recurring AuditHero payroll compliance audit",
            "activities": [
                notebook_activity(
                    "Run Monthly Audit",
                    notebook_id,
                    workspace_id,
                    {
                        "key_vault_url": literal(cfg["key_vault_url"]),
                        "lookback_days": literal(int(monthly.get("lookback_days", 45))),
                        "actual_pay_source": literal(
                            hist.get("actual_pay_source", "PAYROLL_API")
                        ),
                    },
                ),
                notebook_activity(
                    "Refresh Direct Lake and Power BI",
                    bi_notebook_id,
                    workspace_id,
                    {k: literal(v) for k, v in bi_params.items()},
                    depends=["Run Monthly Audit"],
                ),
            ],
        }
    }


def build_wheel(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    script = FABRIC / "scripts" / "build_fabric_wheel.py"
    subprocess.check_call(
        [sys.executable, str(script), "--output-dir", str(output_dir)], cwd=ROOT
    )
    wheels = sorted(
        output_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not wheels:
        raise RuntimeError("AuditHero wheel build produced no .whl")
    return wheels[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(FABRIC / "config" / "fabric.json"))
    ap.add_argument(
        "--skip-run",
        action="store_true",
        help="Deploy definitions but do not execute setup/self-test/BI",
    )
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    ws = cfg["workspace_id"]
    monthly = cfg.get("monthly_schedule", {})
    hist = cfg.get("historical_defaults", {})
    deploy_cfg = cfg.get("deploy", {})
    client = FabricClient(ws, access_token())

    lakehouse_name = cfg.get("lakehouse_name", "AuditHero_Lakehouse")
    environment_name = cfg.get("environment_name", "AuditHero_Environment")
    workspace_name = cfg.get("workspace_name") or ws
    semantic_model_name = cfg.get(
        "semantic_model_name", "AuditHero - SCHADS Payroll Compliance"
    )
    report_name = cfg.get("report_name", semantic_model_name)
    actual_source = hist.get("actual_pay_source", "PAYROLL_API")

    connection_params = {"key_vault_url": cfg["key_vault_url"]}
    historical_params = {
        "key_vault_url": cfg["key_vault_url"],
        "start_date": hist.get("start_date", "2023-07-01"),
        "end_date": hist.get("end_date", "2026-06-30"),
        "actual_pay_source": actual_source,
    }
    monthly_params = {
        "key_vault_url": cfg["key_vault_url"],
        "lookback_days": int(monthly.get("lookback_days", 45)),
        "actual_pay_source": actual_source,
    }
    bi_params = {
        "workspace_name": workspace_name,
        "lakehouse_name": lakehouse_name,
        "semantic_model_name": semantic_model_name,
        "report_name": report_name,
    }

    print("[1/8] Create/update schema-enabled Lakehouse")
    lakehouse = client.create_lakehouse(lakehouse_name)

    print("[2/8] Build + publish Runtime 2.0 Environment")
    environment = client.create_environment(environment_name)
    wheel = build_wheel(ROOT / "dist" / "fabric")
    env_yml = (FABRIC / "environment" / "environment.yml").read_bytes()
    spark_yml = (FABRIC / "environment" / "Sparkcompute.yml").read_bytes()
    client.update_environment(
        environment["id"], env_yml, spark_yml, wheel.read_bytes(), wheel.name
    )

    print("[3/8] Create/update bound parameterized notebooks")
    notebook_specs = {
        "AuditHero - Setup": ("00_setup.py", None),
        "AuditHero - Self Test": ("01_self_test.py", None),
        "AuditHero - Employment Hero Connection": (
            "02_connection_test.py",
            connection_params,
        ),
        "AuditHero - Readiness": ("03_readiness.py", connection_params),
        "AuditHero - Historical Audit": ("04_historical_audit.py", historical_params),
        "AuditHero - Monthly Audit": ("05_monthly_audit.py", monthly_params),
        "AuditHero - Build BI": ("06_build_bi.py", bi_params),
    }
    notebooks = {}
    for name, (file_name, parameters) in notebook_specs.items():
        notebook_code = (FABRIC / "notebooks" / file_name).read_text(encoding="utf-8")
        notebooks[name] = client.upsert_notebook(
            name, notebook_code, lakehouse, environment, parameters
        )

    historical = None
    monthly_pipeline_item = None
    if deploy_cfg.get("create_pipelines", True):
        print("[4/8] Create/update Data Factory pipelines")
        historical = client.upsert_pipeline(
            cfg.get("historical_pipeline_name", "AuditHero - Historical Audit Pipeline"),
            historical_pipeline(
                ws,
                notebooks["AuditHero - Historical Audit"]["id"],
                notebooks["AuditHero - Build BI"]["id"],
                cfg,
                hist,
                bi_params,
            ),
        )
        monthly_pipeline_item = client.upsert_pipeline(
            cfg.get("monthly_pipeline_name", "AuditHero - Monthly Payroll Pipeline"),
            monthly_pipeline(
                ws,
                notebooks["AuditHero - Monthly Audit"]["id"],
                notebooks["AuditHero - Build BI"]["id"],
                cfg,
                monthly,
                hist,
                bi_params,
            ),
        )

        print("[5/8] Create/update monthly schedule")
        client.ensure_monthly_schedule(
            monthly_pipeline_item["id"],
            day=int(monthly.get("day_of_month", 25)),
            time_hhmm=monthly.get("time", "09:00"),
            timezone_id=monthly.get(
                "windows_timezone", "W. Australia Standard Time"
            ),
            enabled=bool(monthly.get("enabled", False)),
        )
    else:
        print("[4-5/8] Pipeline deployment disabled in config")

    run_binding = {
        "lakehouse_id": lakehouse["id"],
        "environment_id": environment["id"],
    }

    if args.skip_run:
        print("[6-8/8] Runtime execution skipped by --skip-run")
    else:
        if deploy_cfg.get("run_setup", True):
            print("[6/8] Execute setup")
            client.run_notebook(
                notebooks["AuditHero - Setup"]["id"],
                **run_binding,
            )
        else:
            print("[6/8] Setup execution disabled in config")

        if deploy_cfg.get("run_self_test", True):
            print("[7/8] Execute Fabric-native regression self-test")
            client.run_notebook(
                notebooks["AuditHero - Self Test"]["id"],
                **run_binding,
            )
        else:
            print("[7/8] Self-test execution disabled in config")

        if deploy_cfg.get("build_semantic_model", True) or deploy_cfg.get(
            "build_report", True
        ):
            print("[8/8] Build/refresh Direct Lake semantic model and Power BI report")
            client.run_notebook(
                notebooks["AuditHero - Build BI"]["id"],
                bi_params,
                **run_binding,
            )
        else:
            print("[8/8] BI deployment disabled in config")

    state = {
        "workspace_id": ws,
        "lakehouse_id": lakehouse["id"],
        "environment_id": environment["id"],
        "historical_pipeline_id": historical["id"] if historical else None,
        "monthly_pipeline_id": (
            monthly_pipeline_item["id"] if monthly_pipeline_item else None
        ),
        "notebooks": {k: v["id"] for k, v in notebooks.items()},
        "semantic_model_name": semantic_model_name,
        "report_name": report_name,
        "monthly_schedule_enabled": bool(monthly.get("enabled", False)),
    }
    out = FABRIC / "deployment_state.json"
    out.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("\nAuditHero Fabric deployment complete")
    print(json.dumps(state, indent=2))
    print(
        "NEXT: add Key Vault secrets -> run connection/readiness -> validate one known "
        "pay period -> run historical audit -> enable monthly schedule."
    )


if __name__ == "__main__":
    main()
