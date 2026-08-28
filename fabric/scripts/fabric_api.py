from __future__ import annotations
import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import requests

FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


def get_access_token() -> str:
    token = os.getenv("FABRIC_TOKEN")
    if token:
        return token.strip()

    tenant = os.getenv("AZURE_TENANT_ID")
    client = os.getenv("AZURE_CLIENT_ID")
    secret = os.getenv("AZURE_CLIENT_SECRET")
    if tenant and client and secret:
        response = requests.post(
            TOKEN_URL.format(tenant=tenant),
            data={
                "client_id": client,
                "client_secret": secret,
                "grant_type": "client_credentials",
                "scope": "https://api.fabric.microsoft.com/.default",
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["access_token"]

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
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        raise RuntimeError(
            "No Fabric authentication found. Set FABRIC_TOKEN, set AZURE_TENANT_ID/"
            "AZURE_CLIENT_ID/AZURE_CLIENT_SECRET, or run 'az login'."
        ) from exc


@dataclass
class FabricResponse:
    status_code: int
    body: Any
    headers: dict


class FabricClient:
    def __init__(self, token: str | None = None, base_url: str = FABRIC_BASE):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token or get_access_token()}",
                "Content-Type": "application/json",
            }
        )

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        body: dict | None = None,
        expected: tuple[int, ...] = (200, 201, 202),
        timeout: int = 120,
        poll_lro: bool = True,
    ) -> FabricResponse:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else f"{self.base_url}/{path_or_url.lstrip('/')}"
        )
        last = None
        for attempt in range(8):
            response = self.session.request(
                method.upper(), url, json=body, timeout=timeout
            )
            last = response
            if response.status_code == 429 or response.status_code >= 500:
                retry = response.headers.get("Retry-After")
                delay = float(retry) if retry else min(2**attempt, 30)
                time.sleep(delay)
                continue
            if response.status_code not in expected:
                detail = response.text[:4000]
                raise RuntimeError(
                    f"Fabric API {method.upper()} {url} returned {response.status_code}: {detail}"
                )
            if response.status_code == 202 and poll_lro:
                location = response.headers.get("Location")
                if location:
                    return self.poll_operation(location)
            return self._wrap(response)
        raise RuntimeError(
            f"Fabric API request exhausted retries: {method} {url}; last={getattr(last,'status_code',None)}"
        )

    @staticmethod
    def _wrap(response: requests.Response) -> FabricResponse:
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = response.text
        return FabricResponse(response.status_code, body, dict(response.headers))

    def poll_operation(self, location: str, timeout_seconds: int = 900) -> FabricResponse:
        started = time.time()
        while True:
            response = self.session.get(location, timeout=120)
            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", 2)))
                continue
            if response.status_code not in (200, 201, 202):
                raise RuntimeError(
                    f"Fabric operation poll returned {response.status_code}: {response.text[:4000]}"
                )
            wrapped = self._wrap(response)
            body = wrapped.body if isinstance(wrapped.body, dict) else {}
            status = str(body.get("status") or body.get("Status") or "").lower()
            if status in ("succeeded", "completed"):
                result_location = response.headers.get("Location") or body.get("resourceLocation")
                if result_location and result_location != location:
                    final = self.session.get(result_location, timeout=120)
                    if final.ok:
                        return self._wrap(final)
                return wrapped
            if status in ("failed", "cancelled", "canceled"):
                raise RuntimeError(f"Fabric long-running operation failed: {json.dumps(body)}")
            # Some Fabric LRO endpoints eventually return the created resource directly.
            if not status and response.status_code in (200, 201) and body.get("id"):
                return wrapped
            if time.time() - started > timeout_seconds:
                raise TimeoutError(f"Fabric operation did not finish within {timeout_seconds}s: {location}")
            time.sleep(float(response.headers.get("Retry-After", 2)))

    def list_items(self, workspace_id: str, item_type: str | None = None) -> list[dict]:
        path = f"workspaces/{workspace_id}/items"
        if item_type:
            path += f"?type={item_type}"
        rows = []
        url = f"{self.base_url}/{path}"
        while url:
            response = self.session.get(url, timeout=120)
            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", 2)))
                continue
            response.raise_for_status()
            body = response.json()
            rows.extend(body.get("value", []))
            url = body.get("continuationUri")
            if not url:
                token = body.get("continuationToken")
                url = f"{self.base_url}/{path}&continuationToken={token}" if token else None
        return rows

    def find_item(self, workspace_id: str, display_name: str, item_type: str) -> dict | None:
        for item in self.list_items(workspace_id, item_type):
            if item.get("displayName") == display_name and item.get("type") == item_type:
                return item
        return None

    def create_or_update_definition_item(
        self,
        *,
        workspace_id: str,
        display_name: str,
        item_type: str,
        collection: str,
        definition: dict,
        description: str = "",
    ) -> dict:
        existing = self.find_item(workspace_id, display_name, item_type)
        if existing:
            self.request(
                "POST",
                f"workspaces/{workspace_id}/{collection}/{existing['id']}/updateDefinition",
                body={"definition": definition},
                expected=(200, 202),
            )
            return existing
        response = self.request(
            "POST",
            f"workspaces/{workspace_id}/{collection}",
            body={
                "displayName": display_name,
                "description": description,
                "definition": definition,
            },
            expected=(201, 202),
        )
        if isinstance(response.body, dict) and response.body.get("id"):
            return response.body
        created = self.find_item(workspace_id, display_name, item_type)
        if not created:
            raise RuntimeError(f"Created {item_type} '{display_name}' but could not resolve its ID")
        return created

    def run_item_job(
        self,
        workspace_id: str,
        item_id: str,
        job_type: str,
        execution_data: dict | None = None,
        timeout_seconds: int = 1800,
    ) -> dict:
        body = {"executionData": execution_data} if execution_data else None
        response = self.request(
            "POST",
            f"workspaces/{workspace_id}/items/{item_id}/jobs/{job_type}/instances",
            body=body,
            expected=(202,),
            poll_lro=False,
        )
        location = response.headers.get("Location")
        if not location:
            raise RuntimeError("Fabric job start did not return a Location header")
        started = time.time()
        while True:
            r = self.session.get(location, timeout=120)
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 2)))
                continue
            r.raise_for_status()
            body = r.json()
            status = str(body.get("status") or "").lower()
            if status in ("completed", "succeeded"):
                return body
            if status in ("failed", "cancelled", "canceled"):
                raise RuntimeError(f"Fabric job failed: {json.dumps(body)}")
            if time.time() - started > timeout_seconds:
                raise TimeoutError(f"Fabric {job_type} job exceeded {timeout_seconds}s")
            time.sleep(5)
