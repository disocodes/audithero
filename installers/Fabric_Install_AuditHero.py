# Fabric notebook source
# METADATA ********************
# META {
# META   "kernel_info": {"name": "synapse_pyspark"},
# META   "language_info": {"name": "python"}
# META }

# CELL ********************

# AuditHero — Install or Upgrade
#
# Import this notebook into the Microsoft Fabric workspace where AuditHero should
# be installed, then choose Run all. The notebook detects the current workspace,
# downloads the selected AuditHero release, creates or updates the managed
# Lakehouse, Environment, notebooks, pipelines, Direct Lake model and Power BI
# report, and runs Setup and Self Test.
#
# Employment Hero credentials are not required. Leave key_vault_url blank when
# you will use uploaded CSV/Excel files.

# CELL ********************

# User settings. The defaults are suitable for a normal file-based installation.
release_ref = "main"
lakehouse_name = "AuditHero_Lakehouse"
environment_name = "AuditHero_Environment"
semantic_model_name = "AuditHero - SCHADS Payroll Compliance"
report_name = "AuditHero - SCHADS Payroll Compliance"
key_vault_url = ""
monthly_schedule_enabled = False
monthly_day_of_month = 25
monthly_time = "09:00"

# CELL ********************

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

import requests


def _context_value(name: str):
    ctx = notebookutils.runtime.context
    if isinstance(ctx, dict):
        return ctx.get(name)
    return getattr(ctx, name, None)


workspace_id = _context_value("currentWorkspaceId")
workspace_name = _context_value("currentWorkspaceName")
if not workspace_id:
    raise RuntimeError("Fabric workspace ID could not be detected from this notebook session.")

print(f"Installing AuditHero into: {workspace_name} ({workspace_id})")
print(f"Release: {release_ref}")

# CELL ********************

# Download the requested public AuditHero release into the notebook's temporary
# working area. The repository archive is used only during installation.
archive_url = f"https://api.github.com/repos/disocodes/audithero/zipball/{release_ref}"
work_dir = Path(tempfile.mkdtemp(prefix="audithero-install-"))
archive_path = work_dir / "audithero.zip"

response = requests.get(archive_url, timeout=180)
response.raise_for_status()
archive_path.write_bytes(response.content)

with zipfile.ZipFile(archive_path) as zf:
    zf.extractall(work_dir / "source")

roots = [p for p in (work_dir / "source").iterdir() if p.is_dir()]
if len(roots) != 1:
    raise RuntimeError("The AuditHero release archive did not contain one repository root.")
repo_root = roots[0]
print(f"Release downloaded to temporary working area: {repo_root.name}")

# CELL ********************

# Build the minimal installation configuration. File-based auditing is enabled
# by default; the API-related Key Vault setting may remain empty.
config = {
    "workspace_id": workspace_id,
    "workspace_name": workspace_name or str(workspace_id),
    "lakehouse_name": lakehouse_name,
    "environment_name": environment_name,
    "semantic_model_name": semantic_model_name,
    "report_name": report_name,
    "key_vault_url": key_vault_url,
    "source_mapping": {
        "source_root": "/lakehouse/default/Files/import/raw",
        "draft_path": "/lakehouse/default/Files/import/source_mapping_draft.xlsx",
        "mapping_path": "/lakehouse/default/Files/import/source_mapping.xlsx",
        "output_root": "/lakehouse/default/Files/input",
        "draft_pipeline_name": "AuditHero - Build Source Mapping Workbook",
        "conversion_pipeline_name": "AuditHero - Convert Source Files",
        "mapped_audit_pipeline_name": "AuditHero - Convert Mapped Files and Run Audit"
    },
    "manual_file_source": {
        "enabled": True,
        "input_root": "/lakehouse/default/Files/input",
        "pipeline_name": "AuditHero - Uploaded Files Audit Pipeline"
    },
    "monthly_schedule": {
        "enabled": bool(monthly_schedule_enabled),
        "day_of_month": int(monthly_day_of_month),
        "time": monthly_time,
        "windows_timezone": "W. Australia Standard Time",
        "lookback_days": 45
    },
    "historical_defaults": {
        "start_date": "2023-07-01",
        "end_date": "2026-06-30",
        "actual_pay_source": "PAYROLL_API"
    },
    "deploy": {
        "run_setup": True,
        "run_self_test": True,
        "build_semantic_model": True,
        "build_report": True,
        "create_pipelines": True
    }
}

config_path = work_dir / "fabric.json"
config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

# CELL ********************

# Fabric supplies a user-scoped token to the notebook. The deployment scripts
# use this token to create only AuditHero-managed items in the current workspace.
os.environ["FABRIC_ACCESS_TOKEN"] = notebookutils.credentials.getToken("pbi")

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--quiet",
    "requests>=2.32", "build>=1.2", "pyyaml>=6.0", "openpyxl>=3.1"
])

steps = [
    repo_root / "fabric" / "scripts" / "deploy_fabric.py",
    repo_root / "fabric" / "scripts" / "deploy_file_source.py",
    repo_root / "fabric" / "scripts" / "deploy_source_mapping.py",
]

for step in steps:
    print(f"Running {step.name} ...")
    subprocess.check_call([sys.executable, str(step), "--config", str(config_path)], cwd=repo_root)

# CELL ********************

print("\nAuditHero installation completed successfully.")
print("Open the Fabric workspace and use these items for normal operation:")
print("  • AuditHero - Build Source Mapping Workbook")
print("  • AuditHero - Convert Mapped Files and Run Audit")
print("  • AuditHero - Uploaded Files Audit Pipeline")
print("  • AuditHero - SCHADS Payroll Compliance (Power BI)")
print("\nUploaded-file auditing is ready without Employment Hero credentials.")
print("The recurring monthly schedule remains disabled unless you enabled it above.")

shutil.rmtree(work_dir, ignore_errors=True)
