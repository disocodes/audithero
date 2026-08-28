#!/usr/bin/env python3
"""Preflight a Fabric AuditHero deployment before creating workspace items."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

import requests

ROOT = Path(__file__).resolve().parents[2]
FABRIC_API = "https://api.fabric.microsoft.com/v1"
REQUIRED_HR_SECRETS = [
    "EH-ORGANISATION-ID",
    "EH-HR-CLIENT-ID",
    "EH-HR-CLIENT-SECRET",
    "EH-HR-REFRESH-TOKEN",
]
OPTIONAL_PAYROLL_SECRETS = ["EH-PAYROLL-API-KEY", "EH-PAYROLL-BUSINESS-ID"]


def _token() -> str | None:
    token = os.getenv("FABRIC_ACCESS_TOKEN")
    if token:
        return token
    if not shutil.which("az"):
        return None
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
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _vault_name(url: str) -> str | None:
    m = re.fullmatch(r"https://([A-Za-z0-9-]+)\.vault\.azure\.net/?", url.strip())
    return m.group(1) if m else None


def _date(value: str, name: str, errors: list[str]) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        errors.append(f"{name} must be YYYY-MM-DD")
        return None


def _validate_config(cfg: dict, errors: list[str], warnings: list[str]):
    workspace_id = str(cfg.get("workspace_id") or "")
    try:
        parsed = UUID(workspace_id)
        if parsed.int == 0:
            errors.append("workspace_id is still the all-zero example value")
    except Exception:
        errors.append("workspace_id must be a valid Fabric workspace GUID")

    vault_url = str(cfg.get("key_vault_url") or "")
    if not _vault_name(vault_url):
        errors.append("key_vault_url must look like https://<vault>.vault.azure.net/")

    for key in ("lakehouse_name", "environment_name", "semantic_model_name", "report_name"):
        if not str(cfg.get(key) or "").strip():
            errors.append(f"{key} must not be blank")

    hist = cfg.get("historical_defaults") or {}
    start = _date(hist.get("start_date", ""), "historical_defaults.start_date", errors)
    end = _date(hist.get("end_date", ""), "historical_defaults.end_date", errors)
    if start and end and start > end:
        errors.append("historical_defaults.start_date must be on/before end_date")
    if str(hist.get("actual_pay_source", "PAYROLL_API")).upper() not in {"PAYROLL_API", "NONE"}:
        errors.append("historical_defaults.actual_pay_source must be PAYROLL_API or NONE")

    monthly = cfg.get("monthly_schedule") or {}
    try:
        day = int(monthly.get("day_of_month", 25))
        if not 1 <= day <= 28:
            warnings.append(
                "monthly_schedule.day_of_month is outside 1-28; months without that day can skip a run"
            )
    except Exception:
        errors.append("monthly_schedule.day_of_month must be an integer")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(monthly.get("time", ""))):
        errors.append("monthly_schedule.time must be HH:MM in 24-hour format")
    try:
        lookback = int(monthly.get("lookback_days", 45))
        if not 1 <= lookback <= 180:
            errors.append("monthly_schedule.lookback_days must be between 1 and 180")
    except Exception:
        errors.append("monthly_schedule.lookback_days must be an integer")
    if monthly.get("enabled") is True:
        warnings.append(
            "monthly_schedule.enabled=true: the recurring audit will be live immediately after deployment"
        )

    deploy = cfg.get("deploy") or {}
    for key in ("run_setup", "run_self_test", "build_semantic_model", "build_report", "create_pipelines"):
        if key in deploy and not isinstance(deploy[key], bool):
            errors.append(f"deploy.{key} must be true or false")


def _check_workspace(workspace_id: str, token: str, errors: list[str], warnings: list[str]):
    try:
        r = requests.get(
            f"{FABRIC_API}/workspaces/{workspace_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if r.status_code == 200:
            payload = r.json()
            print(
                f"Fabric workspace reachable: {payload.get('displayName') or payload.get('name') or workspace_id}"
            )
        elif r.status_code in (401, 403):
            errors.append(
                f"Fabric authentication/permission check failed for workspace ({r.status_code})"
            )
        elif r.status_code == 404:
            errors.append("Fabric workspace_id was not found or is not visible to this identity")
        else:
            warnings.append(f"Fabric workspace preflight returned HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        warnings.append(f"Could not reach Fabric workspace API during preflight: {exc}")


def _check_key_vault(vault_name: str, actual_pay_source: str, errors: list[str], warnings: list[str]):
    if not shutil.which("az"):
        errors.append("Azure CLI is required for --check-secrets")
        return
    required = list(REQUIRED_HR_SECRETS)
    if actual_pay_source.upper() == "PAYROLL_API":
        required += OPTIONAL_PAYROLL_SECRETS
    for secret in required:
        result = subprocess.run(
            [
                "az",
                "keyvault",
                "secret",
                "show",
                "--vault-name",
                vault_name,
                "--name",
                secret,
                "--query",
                "id",
                "-o",
                "tsv",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            errors.append(f"Key Vault secret missing/unreadable for current Azure identity: {secret}")
    if not errors:
        print("Key Vault secret existence check passed for the current Azure identity.")
    else:
        warnings.append(
            "The Fabric notebook identity must independently have Key Vault secret-read permission."
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "fabric/config/fabric.json"))
    ap.add_argument(
        "--check-secrets",
        action="store_true",
        help="Also verify canonical Employment Hero secrets exist in Azure Key Vault using Azure CLI",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Do not call the Fabric workspace API",
    )
    args = ap.parse_args()

    path = Path(args.config)
    if not path.exists():
        print(f"FAILED: missing Fabric config: {path}")
        return 2
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAILED: invalid Fabric config JSON: {exc}")
        return 2

    errors: list[str] = []
    warnings: list[str] = []
    _validate_config(cfg, errors, warnings)

    token = _token()
    if not args.offline:
        if not token:
            errors.append(
                "No Fabric access token available. Run 'az login' or set FABRIC_ACCESS_TOKEN."
            )
        elif not errors:
            _check_workspace(str(cfg["workspace_id"]), token, errors, warnings)

    if args.check_secrets and not errors:
        vault = _vault_name(str(cfg["key_vault_url"]))
        if vault:
            source = str((cfg.get("historical_defaults") or {}).get("actual_pay_source", "PAYROLL_API"))
            _check_key_vault(vault, source, errors, warnings)

    print("\nFabric preflight")
    print(f"  config: {path}")
    print(f"  workspace_id: {cfg.get('workspace_id')}")
    print(f"  lakehouse: {cfg.get('lakehouse_name')}")
    print(f"  environment: {cfg.get('environment_name')}")
    print(f"  monthly enabled: {(cfg.get('monthly_schedule') or {}).get('enabled', False)}")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"  - {item}")
    if errors:
        print("\nFAILED:")
        for item in errors:
            print(f"  - {item}")
        return 1
    print("\nPASS: Fabric configuration and authentication preflight succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
