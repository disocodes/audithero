#!/usr/bin/env python3
"""Validate local Databricks prerequisites before bundle deployment."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

MIN_CLI = (0, 283, 0)


def run(command: list[str]):
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_version(text: str):
    m = re.search(r"(?:v)?(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(x) for x in m.groups()) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="dev")
    ap.add_argument("--skip-warehouse-check", action="store_true")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    exe = shutil.which("databricks")
    if not exe:
        errors.append("Databricks CLI is not installed or not on PATH")
    else:
        version_result = run([exe, "--version"])
        version_text = (version_result.stdout + " " + version_result.stderr).strip()
        version = parse_version(version_text)
        if not version:
            errors.append(f"Could not parse Databricks CLI version from: {version_text}")
        elif version < MIN_CLI:
            errors.append(
                f"Databricks CLI {version_text} is too old; AuditHero requires >= {'.'.join(map(str, MIN_CLI))}"
            )
        else:
            print(f"Databricks CLI: {version_text}")

        auth = run([exe, "current-user", "me", "--output", "json"])
        if auth.returncode != 0:
            errors.append(
                "Databricks authentication failed. Run 'databricks auth login --host https://<workspace>'."
            )
        else:
            try:
                user = json.loads(auth.stdout)
                print(f"Authenticated Databricks identity: {user.get('userName') or user.get('displayName') or user.get('id')}")
            except Exception:
                warnings.append("Databricks authentication succeeded but identity JSON could not be parsed")

        warehouse_id = os.getenv("DATABRICKS_BUNDLE_VAR_sql_warehouse_id", "").strip()
        if not warehouse_id:
            errors.append("DATABRICKS_BUNDLE_VAR_sql_warehouse_id is not set")
        elif not args.skip_warehouse_check and auth.returncode == 0:
            wh = run([exe, "warehouses", "get", warehouse_id, "--output", "json"])
            if wh.returncode != 0:
                errors.append(
                    f"SQL warehouse '{warehouse_id}' cannot be read by the authenticated identity: {wh.stderr.strip()}"
                )
            else:
                try:
                    payload = json.loads(wh.stdout)
                    print(
                        "SQL warehouse: "
                        f"{payload.get('name') or warehouse_id} "
                        f"(state={payload.get('state') or 'unknown'})"
                    )
                except Exception:
                    warnings.append("SQL warehouse lookup succeeded but JSON could not be parsed")

    accounts = os.getenv("DATABRICKS_BUNDLE_VAR_accounts_email", "").strip()
    if not accounts:
        warnings.append(
            "DATABRICKS_BUNDLE_VAR_accounts_email is not set; the bundle defaults the monthly dashboard subscriber to the deploying workspace user."
        )

    print(f"Bundle target: {args.target}")
    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"  - {item}")
    if errors:
        print("\nFAILED:")
        for item in errors:
            print(f"  - {item}")
        return 1
    print("\nPASS: Databricks CLI, authentication and SQL warehouse preflight succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
