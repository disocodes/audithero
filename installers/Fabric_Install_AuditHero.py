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
# report, and runs the initialization sequence.
#
# Employment Hero credentials are optional. Leave key_vault_url blank for
# uploaded CSV/Excel audits.

# CELL ********************

# Installation settings.
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
    """Return the current Fabric runtime context."""
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
    """Read one Fabric runtime value as a plain Python string."""
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
            f"Fabric runtime could not resolve {name} in the current notebook session. "
            "Start a new notebook session and run the AuditHero installer again."
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

# Download the selected AuditHero release into temporary notebook storage.
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
print(f"Release downloaded: {repo_root.name}")

# Verify required installer components before workspace resources are changed.
required_release_files = [
    repo_root / "fabric" / "scripts" / "deploy_fabric.py",
    repo_root / "fabric" / "scripts" / "run_fabric_initialization.py",
    repo_root / "fabric" / "scripts" / "deploy_file_source.py",
    repo_root / "fabric" / "scripts" / "deploy_source_mapping.py",
    repo_root / "fabric" / "scripts" / "deploy_admin_notebooks.py",
    repo_root / "fabric" / "notebooks" / "03e_auto_intake.py",
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

# Build the installation configuration. Key Vault can remain blank for file-based audits.
config = {
    "workspace_id": workspace_id,
    "workspace_name": str(workspace_name or workspace_id),
    "lakehouse_name": str(lakehouse_name),
    "environment_name": str(environment_name),
    "semantic_model_name": str(semantic_model_name),
    "report_name": str(report_name),
    "key_vault_url": str(key_vault_url or ""),
    "auto_file_source": {
        "enabled": True,
        "source_root": "/lakehouse/default/Files/import/raw",
        "output_root": "/lakehouse/default/Files/auto_input",
        "preview_pipeline_name": "AuditHero - Preview Uploaded Files",
        "audit_pipeline_name": "AuditHero - Audit Reviewed Uploaded Files"
    },
    "source_mapping": {
        "source_root": "/lakehouse/default/Files/import/raw",
        "draft_path": "/lakehouse/default/Files/import/source_mapping_draft.xlsx",
        "mapping_path": "/lakehouse/default/Files/import/source_mapping.xlsx",
        "output_root": "/lakehouse/default/Files/input",
        "draft_pipeline_name": "AuditHero - Build Source Mapping Workbook (Advanced)",
        "conversion_pipeline_name": "AuditHero - Convert Source Files (Advanced)",
        "mapped_audit_pipeline_name": "AuditHero - Convert Mapped Files and Run Audit (Advanced)"
    },
    "manual_file_source": {
        "enabled": True,
        "input_root": "/lakehouse/default/Files/input",
        "pipeline_name": "AuditHero - Canonical Files Audit (Advanced)"
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

# Use the current notebook identity for Fabric workspace operations.
os.environ["FABRIC_ACCESS_TOKEN"] = str(notebookutils.credentials.getToken("pbi"))

# Install deployment-only dependencies into an isolated temporary directory so
# the managed Fabric notebook runtime remains unchanged.
bootstrap_deps = work_dir / "bootstrap_deps"
bootstrap_deps.mkdir(parents=True, exist_ok=True)
subprocess.check_call([
    sys.executable,
    "-m",
    "pip",
    "install",
    "--quiet",
    "--disable-pip-version-check",
    "--ignore-installed",
    "--target",
    str(bootstrap_deps),
    "requests>=2.32,<3",
    "build>=1.2,<2",
    "pyyaml>=6,<7",
    "openpyxl>=3.1,<4",
])
print("AuditHero installer dependencies prepared.")

# Deploy managed workspace resources before running the installation validation sequence.
steps = [
    repo_root / "fabric" / "scripts" / "deploy_fabric.py",
    repo_root / "fabric" / "scripts" / "deploy_file_source.py",
    repo_root / "fabric" / "scripts" / "deploy_source_mapping.py",
    repo_root / "fabric" / "scripts" / "deploy_admin_notebooks.py",
    repo_root / "fabric" / "scripts" / "run_fabric_initialization.py",
]


def _run_deployment_step(step: Path) -> None:
    """Run one deployment step and surface its output in this notebook."""
    command = [sys.executable, "-u", str(step), "--config", str(config_path)]
    if step.name == "deploy_fabric.py":
        command.append("--skip-run")
    print(f"Running {step.name} ...", flush=True)

    child_env = os.environ.copy()
    existing_pythonpath = child_env.get("PYTHONPATH", "")
    child_env["PYTHONPATH"] = str(bootstrap_deps) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )

    tail = deque(maxlen=120)
    process = subprocess.Popen(
        command,
        cwd=repo_root,
        env=child_env,
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
            "The final output from that step is included below:\n\n"
            f"{diagnostic}"
        )


for step in steps:
    _run_deployment_step(step)

# CELL ********************

print("\nAuditHero installation completed successfully.")
print("Primary file workflow:")
print("  1. Upload ordinary CSV/XLSX files to Lakehouse Files/import/raw")
print("  2. Run AuditHero - Preview Uploaded Files")
print("  3. Review auto_intake_preview.csv and the prepared data")
print("  4. Run AuditHero - Audit Reviewed Uploaded Files")
print("  5. Open AuditHero - SCHADS Payroll Compliance (Power BI)")
print("Advanced import tools:")
print("  • AuditHero - Build Source Mapping Workbook (Advanced)")
print("  • AuditHero - Convert Mapped Files and Run Audit (Advanced)")
print("Administration notebooks:")
print("  • AuditHero - Install or Upgrade")
print("  • AuditHero - Uninstall")
print("\nUploaded-file auditing is available without Employment Hero credentials.")
print("The monthly schedule remains disabled unless enabled in the installation settings.")

shutil.rmtree(work_dir, ignore_errors=True)

# Remove the imported bootstrap copy after successful first-time installation when
# the managed Install or Upgrade notebook is available.
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
