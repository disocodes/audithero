#!/usr/bin/env python3
"""AuditHero repository release/pre-deployment validator.

Runs without platform credentials and catches structural failures before a Fabric or
Databricks deployment touches a workspace. Optional flags run the Python regression
suite and build the distribution wheel when the corresponding tooling is installed.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SHARED_STAGES = [
    "apply_broken_shift_rules",
    "apply_sleepover_group_rules",
    "apply_rostered_and_daily_overtime",
    "allocate_period_overtime",
    "apply_part_time_pattern_checks",
    "apply_meal_break_events",
    "apply_rest_after_overtime",
    "apply_instrument_history",
    "aggregate_remote_work_events",
    "calculate_supplemental_events",
    "audit_toil_register",
    "reconcile_pay_periods",
]

REQUIRED_KEY_VAULT_SECRETS = [
    "EH-ORGANISATION-ID",
    "EH-HR-CLIENT-ID",
    "EH-HR-CLIENT-SECRET",
    "EH-HR-REFRESH-TOKEN",
]


def fail(errors: list[str], message: str):
    errors.append(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_python(errors: list[str]):
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".venv", "build", "dist", ".git"} for part in path.parts):
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            fail(errors, f"Python syntax error: {path.relative_to(ROOT)}: {exc}")


def validate_json(errors: list[str]):
    for path in sorted(ROOT.rglob("*.json")):
        if any(part in {".venv", "build", "dist", ".git"} for part in path.parts):
            continue
        try:
            load_json(path)
        except Exception as exc:
            fail(errors, f"Invalid JSON: {path.relative_to(ROOT)}: {exc}")


def validate_yaml(errors: list[str], warnings: list[str]):
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        warnings.append("PyYAML not installed; YAML syntax validation skipped.")
        return
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(ROOT.rglob(pattern)):
            if any(part in {".venv", "build", "dist", ".git"} for part in path.parts):
                continue
            try:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception as exc:
                fail(errors, f"Invalid YAML: {path.relative_to(ROOT)}: {exc}")


def validate_rule_library(errors: list[str]):
    award_root = ROOT / "rules" / "MA000100"
    manifest_path = award_root / "manifest.json"
    if not manifest_path.exists():
        fail(errors, "Missing rules/MA000100/manifest.json")
        return
    manifest = load_json(manifest_path)
    for key in ("rates", "conditions", "allowances"):
        refs = manifest.get(key)
        if not isinstance(refs, list) or not refs:
            fail(errors, f"Rule manifest has no {key} entries")
            continue
        seen_paths: set[str] = set()
        for rel in refs:
            if rel in seen_paths:
                fail(errors, f"Duplicate manifest path in {key}: {rel}")
            seen_paths.add(rel)
            path = award_root / rel
            if not path.exists():
                fail(errors, f"Manifest references missing file: rules/MA000100/{rel}")
                continue
            payload = load_json(path)
            if payload.get("award_code") != "MA000100":
                fail(errors, f"Wrong/missing award_code in {rel}")
            try:
                date.fromisoformat(str(payload["operative_date"])[:10])
            except Exception:
                fail(errors, f"Invalid operative_date in {rel}")
            source = payload.get("source") or {}
            if not source.get("url") or not source.get("verification_status"):
                fail(errors, f"Missing source URL/verification status in {rel}")
            if key == "rates":
                rows = payload.get("rates") or []
                codes = [r.get("classification_code") for r in rows]
                if not rows:
                    fail(errors, f"No rates in {rel}")
                if len(codes) != len(set(codes)):
                    fail(errors, f"Duplicate classification_code in {rel}")
                for row in rows:
                    try:
                        if float(row["base_hourly_rate"]) <= 0:
                            raise ValueError("not positive")
                    except Exception:
                        fail(errors, f"Invalid base_hourly_rate in {rel}: {row}")
            elif key == "allowances":
                rows = payload.get("allowances") or []
                keys = [r.get("key") for r in rows]
                if len(keys) != len(set(keys)):
                    fail(errors, f"Duplicate allowance key in {rel}")
            elif key == "conditions":
                for required in (
                    "ordinary_penalties",
                    "minimum_engagement",
                    "overtime",
                    "sleepover",
                ):
                    if required not in payload:
                        fail(errors, f"Missing {required} in condition pack {rel}")


def validate_platform_parity(errors: list[str]):
    fabric = (ROOT / "src/schads_audit/fabric_pipeline.py").read_text(encoding="utf-8")
    databricks = (ROOT / "src/schads_audit/databricks_pipeline_v2.py").read_text(encoding="utf-8")
    for stage in SHARED_STAGES:
        if stage not in fabric:
            fail(errors, f"Fabric pipeline missing shared stage: {stage}")
        if stage not in databricks:
            fail(errors, f"Databricks pipeline missing shared stage: {stage}")

    for path in ("notebooks/03_historical_audit.py", "notebooks/04_monthly_payroll_audit.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        if "run_databricks_audit_v2" not in text:
            fail(errors, f"Canonical Databricks notebook bypasses complete engine: {path}")

    for path in ("fabric/notebooks/04_historical_audit.py", "fabric/notebooks/05_monthly_audit.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        if "publish_current_snapshots" not in text:
            fail(errors, f"Fabric successful audit does not publish Direct Lake snapshots: {path}")


def validate_deployment_contracts(errors: list[str], warnings: list[str]):
    # Fabric dependency is intentionally pinned because the semantic model/report
    # APIs have changed between Semantic Link Labs releases.
    env = (ROOT / "fabric/environment/environment.yml").read_text(encoding="utf-8")
    if "semantic-link-labs==0.15.2" not in env:
        fail(errors, "Fabric Environment must pin semantic-link-labs==0.15.2")

    fabric_example = load_json(ROOT / "fabric/config/fabric.example.json")
    monthly = fabric_example.get("monthly_schedule", {})
    if monthly.get("enabled") is not False:
        fail(errors, "Fabric example monthly schedule must default to disabled")
    if not str(fabric_example.get("key_vault_url", "")).startswith("https://"):
        fail(errors, "Fabric example key_vault_url must be HTTPS")

    jobs = (ROOT / "resources/jobs.yml").read_text(encoding="utf-8")
    if "pause_status: PAUSED" not in jobs:
        fail(errors, "Databricks monthly schedule must default to PAUSED")
    if "03_historical_audit.py" not in jobs or "04_monthly_payroll_audit.py" not in jobs:
        fail(errors, "Databricks canonical jobs do not reference canonical audit notebooks")

    fabric_deploy = (ROOT / "fabric/scripts/deploy.sh").read_text(encoding="utf-8")
    if "deploy_fabric.py" not in fabric_deploy:
        fail(errors, "Fabric shell entrypoint does not invoke deploy_fabric.py")
    for legacy in ("deploy_fabric_complete.py", "deploy_fabric_final.py"):
        if (ROOT / "fabric/scripts" / legacy).exists():
            fail(errors, f"Legacy Fabric installer still exists: {legacy}")

    # Local/controlled data must never be committed accidentally.
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    required_ignores = [
        "fabric/config/fabric.json",
        "fabric/deployment_state.json",
        "config/industrial_instrument_history.csv",
        "config/part_time_patterns.csv",
        "config/part_time_variations.csv",
        "config/meal_break_events.csv",
        "config/overtime_rest_controls.csv",
        "config/supplemental_events.csv",
        "config/toil_register.csv",
    ]
    for item in required_ignores:
        if item not in ignore:
            fail(errors, f"Sensitive/local file missing from .gitignore: {item}")

    # Ensure fixed Key Vault secret contract remains documented.
    key_vault_doc = (ROOT / "fabric/docs/KEY_VAULT.md").read_text(encoding="utf-8")
    for secret in REQUIRED_KEY_VAULT_SECRETS:
        if secret not in key_vault_doc:
            fail(errors, f"Key Vault documentation missing secret: {secret}")

    # Semantic model helper must build over current physical snapshot tables.
    bi = (ROOT / "fabric/notebooks/06_build_bi.py").read_text(encoding="utf-8")
    for table in (
        "gold.current_reconciliation",
        "gold.current_audit_detail",
        "gold.current_event_adjustments",
        "gold.current_toil_findings",
    ):
        if table not in bi:
            fail(errors, f"Fabric Direct Lake model missing snapshot table: {table}")

    if "REQUIRES_REVIEW" not in bi or "Potential Underpayment" not in bi:
        warnings.append("Could not confirm remediation-safe DAX wording in BI notebook.")


def run_command(errors: list[str], command: list[str], label: str):
    print(f"\n== {label} ==")
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except FileNotFoundError:
        fail(errors, f"Required command not installed for {label}: {command[0]}")
    except subprocess.CalledProcessError as exc:
        fail(errors, f"{label} failed with exit code {exc.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-pytest", action="store_true", help="Run pytest -q after structural checks")
    ap.add_argument("--build-wheel", action="store_true", help="Build a wheel into dist/validation")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    print("AuditHero repository preflight")
    validate_python(errors)
    validate_json(errors)
    validate_yaml(errors, warnings)
    validate_rule_library(errors)
    validate_platform_parity(errors)
    validate_deployment_contracts(errors, warnings)

    if args.with_pytest and not errors:
        run_command(errors, [sys.executable, "-m", "pytest", "-q"], "Python regression suite")
    if args.build_wheel and not errors:
        out = ROOT / "dist" / "validation"
        out.mkdir(parents=True, exist_ok=True)
        run_command(
            errors,
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
            "Wheel build",
        )

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        print("\nFAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("\nPASS: repository structure, rules and platform contracts are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
