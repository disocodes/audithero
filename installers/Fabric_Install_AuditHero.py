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

from collections import deque
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

import requests


def _runtime_context():
    """Return Fabric runtime context without retaining a Py4J method proxy."""
    ctx = notebookutils.runtime.context
    if isinstance(ctx, dict):
        return ctx
    if callable(ctx):
        try:
            resolved = ctx()
            if resolved is not None:
                return resolved
        except Exception:
            pass
    return ctx


def _context_value(name: str):
    """Read one Fabric context value and return only a plain Python string."""
    ctx = _runtime_context()
    value = None

    if isinstance(ctx, dict):
        value = ctx.get(name)
    else:
        try:
            value = ctx[name]
        except Exception:
            getter = getattr(ctx, "get", None)
            if callable(getter):
                try:
                    value = getter(name)
                except Exception:
                    value = None

        # Compatibility fallback for runtime bridge objects exposing zero-argument methods.
        if value is None:
            member = getattr(ctx, name, None)
            if callable(member):
                try:
                    value = member()
                except Exception:
                    value = None

    if value is None:
        return None

    module_name = type(value).__module__
    type_name = type(value).__name__
    if module_name.startswith("py4j") or type_name == "JavaMember":
        raise RuntimeError(
            f"Fabric runtime returned an unresolved Py4J object for {name}. "
            "Start a fresh notebook session and rerun the current AuditHero installer."
        )
    return str(value).strip()


workspace_id = _context_value("currentWorkspaceId")
workspace_name = _context_value("currentWorkspaceName")
current_notebook_id = _context_value("currentNotebookId")
current_notebook_name = _context_value("currentNotebookName")

if not workspace_id:
    raise RuntimeError("Fabric workspace ID could not be detected from this notebook session.")
try:
    workspace_id = str(uuid.UUID(workspace_id))
except ValueError as exc:
    raise RuntimeError(f"Fabric returned an invalid workspace ID: {workspace_id!r}") from exc

print(f"Installing AuditHero into: {workspace_name or 'current workspace'} ({workspace_id})")
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

# Required support files must be present in the selected release before any
# workspace resources are changed.
required_release_files = [
    repo_root / "fabric" / "scripts" / "deploy_fabric.py",
    repo_root / "fabric" / "scripts" / "deploy_file_source.py",
    repo_root / "fabric" / "scripts" / "deploy_source_mapping.py",
    repo_root / "fabric" / "scripts" / "deploy_admin_notebooks.py",
    repo_root / "installers" / "Fabric_Install_AuditHero.py",
    repo_root / "installers" / "Fabric_Uninstall_AuditHero.py",
]
missing_release_files = [str(p.relative_to(repo_root)) for p in required_release_files if not p.exists()]
if missing_release_files:
    raise RuntimeError(
        "The selected AuditHero release is missing installer components: "
        + ", ".join(missing_release_files)
    )

# CELL ********************

# Build the installation configuration. File-based auditing is enabled by
# default; the API-related Key Vault setting may remain empty.
config = {
    "workspace_id": workspace_id,
    "workspace_name": str(workspace_name or workspace_id),
    "lakehouse_name": str(lakehouse_name),
    "environment_name": str(environment_name),
    "semantic_model_name": str(semantic_model_name),
    "report_name": str(report_name),
    "key_vault_url": str(key_vault_url or ""),
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
        "time": str(monthly_time),
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
# use this token to create AuditHero-managed items in the current workspace.
os.environ["FABRIC_ACCESS_TOKEN"] = str(notebookutils.credentials.getToken("pbi"))

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--quiet",
    "requests>=2.32", "build>=1.2", "pyyaml>=6.0", "openpyxl>=3.1"
])

steps = [
    repo_root / "fabric" / "scripts" / "deploy_fabric.py",
    repo_root / "fabric" / "scripts" / "deploy_file_source.py",
    repo_root / "fabric" / "scripts" / "deploy_source_mapping.py",
    repo_root / "fabric" / "scripts" / "deploy_admin_notebooks.py",
]


def _run_deployment_step(step: Path) -> None:
    """Run one deployer while preserving the real Fabric error in notebook output."""
    command = [sys.executable, "-u", str(step), "--config", str(config_path)]
    print(f"Running {step.name} ...", flush=True)

    # Fabric notebook cells can otherwise surface only CalledProcessError from
    # subprocess.check_call. Stream the child output live and keep a bounded
    # tail so the underlying REST/API error is repeated in the raised exception.
    tail = deque(maxlen=80)
    process = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError(f"Unable to capture output from installer step {step.name}.")

    for line in process.stdout:
        print(line, end="", flush=True)
        tail.append(line.rstrip())

    return_code = process.wait()
    if return_code != 0:
        diagnostic = "\n".join(tail)
        raise RuntimeError(
            f"AuditHero installer step {step.name} failed with exit code {return_code}.\n"
            "The final output from that step is repeated below so Fabric does not "
            "hide the underlying error:\n\n"
            f"{diagnostic}"
        )


for step in steps:
    _run_deployment_step(step)

# CELL ********************

print("\nAuditHero installation completed successfully.")
print("Open the Fabric workspace and use these items for normal operation:")
print("  • AuditHero - Build Source Mapping Workbook")
print("  • AuditHero - Convert Mapped Files and Run Audit")
print("  • AuditHero - Uploaded Files Audit Pipeline")
print("  • AuditHero - SCHADS Payroll Compliance (Power BI)")
print("Administration notebooks are also installed:")
print("  • AuditHero - Install or Upgrade")
print("  • AuditHero - Uninstall")
print("\nUploaded-file auditing is ready without Employment Hero credentials.")
print("The recurring monthly schedule remains disabled unless you enabled it above.")

shutil.rmtree(work_dir, ignore_errors=True)

# If this was the one-time imported bootstrap copy, remove it after success. The
# managed 'AuditHero - Install or Upgrade' notebook has already been installed.
if current_notebook_id and current_notebook_name != "AuditHero - Install or Upgrade":
    try:
        token = os.environ["FABRIC_ACCESS_TOKEN"]
        cleanup = requests.delete(
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{current_notebook_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        if cleanup.status_code not in (200, 202, 204, 404):
            print(f"Bootstrap notebook cleanup was not completed automatically: {cleanup.status_code}")
    except Exception as exc:
        print(f"Bootstrap notebook cleanup was not completed automatically: {exc}")
