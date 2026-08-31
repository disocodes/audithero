#!/usr/bin/env python3
"""Offline AuditHero repository preflight.

Runs before either Fabric or Databricks deployment. Employment Hero credentials
are intentionally optional because AuditHero supports CSV/XLSX auditing as a
first-class source path.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(msg, errors):
    errors.append(msg); print(f"FAIL  {msg}")
def ok(msg): print(f"OK    {msg}")


def check_python(errors):
    files = sorted(
        p for base in (
            ROOT/"src",ROOT/"notebooks",ROOT/"fabric"/"notebooks",ROOT/"fabric"/"scripts",
            ROOT/"installers",ROOT/"scripts",ROOT/"tools"
        ) if base.exists() for p in base.rglob("*.py")
    )
    for p in files:
        try: ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
        except SyntaxError as exc: fail(f"Python syntax {p.relative_to(ROOT)}:{exc.lineno}: {exc.msg}",errors)
    if not any("Python syntax" in x for x in errors): ok(f"Python syntax ({len(files)} files)")


def check_json(errors):
    files=sorted(p for p in ROOT.rglob("*.json") if ".git" not in p.parts and "dist" not in p.parts)
    for p in files:
        if p.name=="fabric.json": continue
        try: json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc: fail(f"JSON {p.relative_to(ROOT)}: {exc}",errors)
    if not any(x.startswith("JSON ") for x in errors): ok(f"JSON parse ({len(files)} files)")


def check_yaml(errors):
    try: import yaml
    except ImportError:
        print("SKIP  YAML parse (install pyyaml for this check)"); return
    files=sorted(list(ROOT.rglob("*.yml"))+list(ROOT.rglob("*.yaml")))
    for p in files:
        try: yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as exc: fail(f"YAML {p.relative_to(ROOT)}: {exc}",errors)
    if not any(x.startswith("YAML ") for x in errors): ok(f"YAML parse ({len(files)} files)")


def check_rules(errors):
    rule_root=ROOT/"rules"/"MA000100"; manifest_path=rule_root/"manifest.json"
    if not manifest_path.exists(): fail("Missing rules/MA000100/manifest.json",errors); return
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("award_code")!="MA000100": fail("Rule manifest award_code is not MA000100",errors)
    for key in ("rates","conditions","allowances"):
        refs=manifest.get(key) or []
        if not refs: fail(f"Rule manifest has no {key}",errors); continue
        for r in refs:
            p=rule_root/r
            if not p.exists(): fail(f"Rule manifest missing referenced file: {r}",errors)
            else:
                pack=json.loads(p.read_text(encoding="utf-8")); source=pack.get("source") or {}
                if not pack.get("operative_date"): fail(f"{r} has no operative_date",errors)
                if not source.get("publisher") or not source.get("url"): fail(f"{r} lacks source publisher/url",errors)
    if not any("Rule manifest" in x or "operative_date" in x or "source publisher" in x for x in errors): ok("SCHADS manifest and referenced packs")


def check_required_files(errors,platform):
    common=[
        "README.md","QUICKSTART.md","pyproject.toml",
        "docs/README.md","docs/IMPORT_AND_FIELD_MAPPING.md","docs/AUDIT_DATA_REQUIREMENTS.md",
        "docs/RUNNING_AUDITS.md","docs/UNDERSTANDING_RESULTS.md","docs/NOTEBOOK_REFERENCE.md",
        "src/schads_audit/engine.py","src/schads_audit/rules.py","src/schads_audit/file_source.py",
        "src/schads_audit/manual_audit.py","src/schads_audit/source_mapping.py","src/schads_audit/mapping_workbook.py",
        "config/source_mapping.example.json","tools/build_input_workbook.py",
        "tests/test_platform_parity.py","tests/test_source_mapping.py","tests/test_mapping_workbook.py",
    ]
    fabric=[
        "installers/Fabric_Install_AuditHero.py","installers/Fabric_Uninstall_AuditHero.py",
        "docs/INSTALL_FABRIC_UI.md","fabric/README.md","fabric/config/fabric.example.json",
        "fabric/scripts/deploy.sh","fabric/scripts/deploy.ps1","fabric/scripts/deploy_fabric.py",
        "fabric/scripts/deploy_file_source.py","fabric/scripts/deploy_source_mapping.py",
        "fabric/notebooks/00_setup.py","fabric/notebooks/01_self_test.py",
        "fabric/notebooks/03b_file_readiness.py","fabric/notebooks/03c_source_mapping_draft.py",
        "fabric/notebooks/03d_convert_source_files.py","fabric/notebooks/04_historical_audit.py",
        "fabric/notebooks/04b_manual_file_audit.py","fabric/notebooks/05_monthly_audit.py",
        "fabric/notebooks/06_build_bi.py",
    ]
    databricks=[
        "installers/Databricks_Install_AuditHero.py","installers/Databricks_Uninstall_AuditHero.py",
        "docs/INSTALL_DATABRICKS_UI.md","databricks/README.md","databricks.yml",
        "resources/jobs.yml","resources/dashboard.yml",
        "scripts/deploy.sh","scripts/deploy.ps1","scripts/configure_secrets.sh","scripts/configure_secrets.ps1",
        "notebooks/00_setup.py","notebooks/01b_self_test.py","notebooks/02c_file_readiness.py",
        "notebooks/02d_source_mapping_draft.py","notebooks/02e_convert_source_files.py",
        "notebooks/03_historical_audit.py","notebooks/03b_manual_file_audit.py","notebooks/04_monthly_payroll_audit.py",
    ]
    selected=common+(fabric if platform in ("fabric","all") else [])+(databricks if platform in ("databricks","all") else [])
    for rel in selected:
        if not (ROOT/rel).exists(): fail(f"Missing required file: {rel}",errors)
    if not any(x.startswith("Missing required file") for x in errors): ok(f"Required {platform} deployment files")


def check_fabric_config(path,errors):
    if not path: return
    p=Path(path); p=p if p.is_absolute() else ROOT/p
    if not p.exists(): fail(f"Fabric config not found: {p}",errors); return
    cfg=json.loads(p.read_text(encoding="utf-8")); ws=str(cfg.get("workspace_id") or "")
    if not ws or ws.startswith("00000000-"): fail("Fabric workspace_id is still the example placeholder",errors)
    kv=str(cfg.get("key_vault_url") or "").strip()
    if kv and (not kv.startswith("https://") or "your-key-vault" in kv):
        fail("Fabric key_vault_url is invalid; leave it blank for file-only mode or configure a real vault",errors)
    if not kv: print("OK    Key Vault omitted: CSV/XLSX mode can deploy without Employment Hero credentials")
    schedule=cfg.get("monthly_schedule") or {}
    if schedule.get("enabled",False): print("WARN  Fabric monthly schedule is enabled; validate one pay period first")
    else: ok("Fabric monthly schedule disabled by default")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--platform",choices=["all","fabric","databricks"],default="all"); ap.add_argument("--fabric-config",default=None); args=ap.parse_args()
    errors=[]; print("AuditHero offline preflight\n")
    check_python(errors); check_json(errors); check_yaml(errors); check_rules(errors); check_required_files(errors,args.platform)
    if args.platform in ("fabric","all") and args.fabric_config: check_fabric_config(args.fabric_config,errors)
    print()
    if errors:
        print(f"PRECHECK FAILED: {len(errors)} issue(s)"); [print(f" - {e}") for e in errors]; return 1
    print("PRECHECK PASSED"); return 0

if __name__=="__main__": raise SystemExit(main())
