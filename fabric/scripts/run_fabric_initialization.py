#!/usr/bin/env python3
"""Run AuditHero Fabric initialization notebooks with structured diagnostics.

Resource deployment and Spark execution are intentionally separated. The deployer
creates/updates Fabric items with --skip-run; this driver then verifies the
published AuditHero custom wheel, repairs it through Fabric's stable staging API
when necessary, and executes Setup, Self Test, and Build BI through the notebook
Job Scheduler API while inspecting each notebook exitValue.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

API = "https://api.fabric.microsoft.com/v1"
ROOT = Path(__file__).resolve().parents[2]
FABRIC = ROOT / "fabric"


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


def _parameter_type(value: Any) -> str:
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "Number"
    return "Text"


class FabricRuntimeClient:
    def __init__(self, workspace_id: str, token: str):
        self.workspace_id = workspace_id
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{API}{path}"

    def request(self, method: str, path: str, *, body=None):
        url = self._url(path)
        for attempt in range(8):
            r = self.session.request(method, url, json=body, timeout=120)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", min(60, 2**attempt))))
                continue
            if r.status_code not in (200, 201, 202, 204):
                raise RuntimeError(f"Fabric {method} {url} -> {r.status_code}: {r.text}")
            if not r.content:
                return None
            try:
                return r.json()
            except ValueError:
                return r.text
        raise RuntimeError(f"Fabric request remained rate-limited: {method} {url}")

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

    def wait_environment_publish(self, environment_id: str) -> dict:
        deadline = time.time() + 1800
        last_state = None
        while time.time() < deadline:
            payload = self.request(
                "GET",
                f"/workspaces/{self.workspace_id}/environments/{environment_id}",
            )
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
        raise TimeoutError(
            f"Timed out waiting for Fabric Environment {environment_id} to publish"
        )

    def published_libraries(self, environment_id: str) -> list[dict]:
        """Return effective published Environment libraries using the stable API."""
        path = (
            f"/workspaces/{self.workspace_id}/environments/{environment_id}"
            "/libraries?beta=false"
        )
        libraries: list[dict] = []
        while path:
            payload = self.request("GET", path)
            if not isinstance(payload, dict):
                break
            libraries.extend(payload.get("libraries") or [])
            continuation_uri = payload.get("continuationUri")
            token = payload.get("continuationToken")
            if continuation_uri and str(continuation_uri).lower() not in {"null", "none"}:
                path = str(continuation_uri)
            elif token and str(token).lower() not in {"null", "none"}:
                path = (
                    f"/workspaces/{self.workspace_id}/environments/{environment_id}"
                    f"/libraries?beta=false&continuationToken={quote(str(token), safe='')}"
                )
            else:
                path = None
        return libraries

    def upload_custom_library(self, environment_id: str, wheel_path: Path) -> None:
        """Upload one wheel with Fabric's stable application/octet-stream API."""
        url = self._url(
            f"/workspaces/{self.workspace_id}/environments/{environment_id}"
            f"/staging/libraries/{quote(wheel_path.name, safe='')}"
        )
        data = wheel_path.read_bytes()
        for attempt in range(8):
            r = self.session.post(
                url,
                data=data,
                headers={"Content-Type": "application/octet-stream"},
                timeout=180,
            )
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", min(60, 2**attempt))))
                continue
            if r.status_code not in (200, 201, 202, 204):
                raise RuntimeError(
                    f"Fabric custom-library upload {url} -> {r.status_code}: {r.text}"
                )
            return
        raise RuntimeError(f"Fabric custom-library upload remained rate-limited: {url}")

    def ensure_audithero_wheel(self, environment_id: str) -> str:
        """Ensure the wheel is effective, repairing staging/publish when absent."""
        wheels = sorted(
            (ROOT / "dist" / "fabric").glob("audithero_schads-*.whl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not wheels:
            raise RuntimeError(
                "AuditHero Fabric wheel is missing from dist/fabric after deployment."
            )
        wheel = wheels[0]

        published = self.published_libraries(environment_id)
        published_names = {
            str(x.get("name"))
            for x in published
            if isinstance(x, dict) and x.get("libraryType") == "Custom"
        }
        if wheel.name in published_names:
            print(f"    Published custom library verified: {wheel.name}", flush=True)
            return wheel.name

        print(
            f"    AuditHero wheel is not effective in the published Environment; "
            f"uploading {wheel.name} through the stable staging API...",
            flush=True,
        )
        self.upload_custom_library(environment_id, wheel)
        self.request(
            "POST",
            f"/workspaces/{self.workspace_id}/environments/{environment_id}"
            "/staging/publish?beta=false",
        )
        self.wait_environment_publish(environment_id)

        published = self.published_libraries(environment_id)
        published_names = {
            str(x.get("name"))
            for x in published
            if isinstance(x, dict) and x.get("libraryType") == "Custom"
        }
        if wheel.name not in published_names:
            raise RuntimeError(
                "Fabric reported Environment publish Success, but the AuditHero wheel "
                f"is still absent from the published library list: {wheel.name}. "
                f"Published custom libraries: {sorted(published_names)}"
            )
        print(f"    Published custom library verified: {wheel.name}", flush=True)
        return wheel.name

    @staticmethod
    def _monitoring(payload: dict) -> dict:
        properties = payload.get("properties") if isinstance(payload, dict) else {}
        if not isinstance(properties, dict):
            properties = {}
        compute_details = properties.get("computeDetails")
        if not isinstance(compute_details, dict):
            compute_details = {}
        monitoring = compute_details.get("monitoringInfo")
        return monitoring if isinstance(monitoring, dict) else {}

    @staticmethod
    def _exit_value(payload: dict) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("exitValue")
        if value is not None:
            return str(value)
        properties = payload.get("properties")
        if isinstance(properties, dict) and properties.get("exitValue") is not None:
            return str(properties.get("exitValue"))
        return None

    @staticmethod
    def _print_failure_summary(label: str, detail: dict) -> None:
        """Print one compact line before a long traceback can obscure the real cause."""
        stage = detail.get("stage") or "unknown"
        exc_type = detail.get("exception_type") or detail.get("errorCode") or "RuntimeError"
        message = detail.get("message") or detail.get("failureReason") or detail.get("rawExitValue") or "Unknown failure"
        if isinstance(message, (dict, list)):
            message = json.dumps(message, separators=(",", ":"), default=str)
        message = str(message).replace("\n", " ").strip()
        if len(message) > 1200:
            message = message[:1200] + "..."
        print(
            f"    AUDITHERO FAILURE SUMMARY | label={label} | stage={stage} "
            f"| exception={exc_type} | message={message}",
            flush=True,
        )
        print(
            "    AUDITHERO FAILURE JSON: "
            + json.dumps(detail, separators=(",", ":"), default=str)[:4000],
            flush=True,
        )

    def run_notebook(
        self,
        item_id: str,
        *,
        lakehouse_id: str,
        environment_id: str,
        parameters: dict[str, Any] | None = None,
        label: str,
    ) -> dict:
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
            "/jobs/execute/instances?jobType=RunNotebook"
        )
        r = self.session.post(url, json=body, timeout=120)
        if r.status_code != 202:
            raise RuntimeError(f"Fabric POST {url} -> {r.status_code}: {r.text}")

        location = r.headers.get("Location", "")
        job_id = location.rstrip("/").split("/")[-1] if location else ""
        if not job_id:
            raise RuntimeError(
                f"Fabric accepted {label} but returned no job instance Location"
            )

        poll_path = (
            f"/workspaces/{self.workspace_id}/notebooks/{item_id}"
            f"/jobs/execute/instances/{job_id}?beta=true"
        )
        print(f"    {label} job: {job_id}", flush=True)
        deadline = time.time() + 1800
        delay = max(2, int(r.headers.get("Retry-After", "10")))
        last_status = None

        while time.time() < deadline:
            time.sleep(min(delay, 30))
            payload = self.request("GET", poll_path)
            if not isinstance(payload, dict):
                continue

            status = str(payload.get("status") or "").strip()
            if status and status != last_status:
                print(f"    {label} status: {status}", flush=True)
                last_status = status

            normalized = status.lower()
            if normalized in {"completed", "succeeded", "success"}:
                exit_value = self._exit_value(payload)
                if exit_value and exit_value.startswith("AUDITHERO_ERROR:"):
                    raw = exit_value.split(":", 1)[1]
                    try:
                        detail = json.loads(raw)
                    except Exception:
                        detail = {"rawExitValue": exit_value}
                    self._print_failure_summary(label, detail)
                    raise RuntimeError(
                        f"{label} reported an AuditHero runtime error:\n"
                        + json.dumps(detail, indent=2, default=str)
                    )
                if payload.get("failureReason"):
                    detail = {
                        "stage": "Fabric job completion",
                        "failureReason": payload.get("failureReason"),
                        "message": payload.get("failureReason"),
                        "monitoring": self._monitoring(payload),
                    }
                    self._print_failure_summary(label, detail)
                    raise RuntimeError(
                        f"{label} completed with failureReason: "
                        + json.dumps(payload.get("failureReason"), default=str)
                    )
                if exit_value:
                    print(f"    {label} exitValue: {exit_value[:500]}", flush=True)
                return payload

            if normalized in {"failed", "cancelled", "canceled"}:
                detail = {
                    "jobInstanceId": job_id,
                    "stage": "Fabric notebook job",
                    "failureReason": payload.get("failureReason"),
                    "message": payload.get("failureReason"),
                    "exitValue": self._exit_value(payload),
                    "monitoring": self._monitoring(payload),
                    "rootActivityId": payload.get("rootActivityId"),
                }
                self._print_failure_summary(label, detail)
                raise RuntimeError(
                    f"{label} Fabric job failed:\n"
                    + json.dumps(detail, indent=2, default=str)
                )

        raise TimeoutError(f"Timed out waiting for {label} job {job_id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(FABRIC / "config" / "fabric.json"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    state_path = FABRIC / "deployment_state.json"
    if not state_path.exists():
        raise RuntimeError(
            "Fabric deployment_state.json is missing. Run deploy_fabric.py --skip-run first."
        )
    state = json.loads(state_path.read_text(encoding="utf-8"))

    ws = cfg["workspace_id"]
    client = FabricRuntimeClient(ws, access_token())
    notebooks = state["notebooks"]
    lakehouse_id = state["lakehouse_id"]
    environment_id = state["environment_id"]
    deploy_cfg = cfg.get("deploy", {})

    print("[5.5/8] Verify published AuditHero Environment library")
    client.ensure_audithero_wheel(environment_id)

    if deploy_cfg.get("run_setup", True):
        print("[6/8] Execute setup with structured diagnostics")
        client.run_notebook(
            notebooks["AuditHero - Setup"],
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            label="AuditHero Setup",
        )
    else:
        print("[6/8] Setup execution disabled in config")

    if deploy_cfg.get("run_self_test", True):
        print("[7/8] Execute Fabric-native regression self-test")
        client.run_notebook(
            notebooks["AuditHero - Self Test"],
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            label="AuditHero Self Test",
        )
    else:
        print("[7/8] Self-test execution disabled in config")

    if deploy_cfg.get("build_semantic_model", True) or deploy_cfg.get(
        "build_report", True
    ):
        print("[8/8] Build/refresh Direct Lake semantic model and Power BI report")
        bi_params = {
            "workspace_name": cfg.get("workspace_name") or ws,
            "lakehouse_name": cfg.get("lakehouse_name", "AuditHero_Lakehouse"),
            "semantic_model_name": cfg.get(
                "semantic_model_name", "AuditHero - SCHADS Payroll Compliance"
            ),
            "report_name": cfg.get(
                "report_name", "AuditHero - SCHADS Payroll Compliance"
            ),
        }
        client.run_notebook(
            notebooks["AuditHero - Build BI"],
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            parameters=bi_params,
            label="AuditHero Build BI",
        )
    else:
        print("[8/8] BI deployment disabled in config")

    print("AuditHero Fabric runtime initialization complete")


if __name__ == "__main__":
    main()
