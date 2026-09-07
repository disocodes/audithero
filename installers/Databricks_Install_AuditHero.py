# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Install or Upgrade
# MAGIC
# MAGIC Production installer and upgrader for AuditHero on Databricks.
# MAGIC
# MAGIC **Run all** performs the following controlled phases:
# MAGIC 1. validates and imports the selected AuditHero release;
# MAGIC 2. resolves shared Databricks resources;
# MAGIC 3. creates or updates AuditHero Jobs;
# MAGIC 4. runs environment Setup;
# MAGIC 5. validates and publishes the managed AI/BI dashboard;
# MAGIC 6. runs the synthetic SCHADS calculation Self Test;
# MAGIC 7. records installation state.
# MAGIC
# MAGIC Each execution phase raises on failure. Setup, dashboard deployment and Self Test are separate cells so their status and diagnostics are independently visible.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Installer dependencies
# MAGIC Installs the packages required to call Databricks APIs, download the selected release and parse the AuditHero resource manifest.
# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20" "pyyaml>=6.0" "requests>=2.32"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Installation settings
# MAGIC Configure the release and Databricks resource settings. Existing compatible resources are reused where possible.
# COMMAND ----------
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
secret_scope = "audithero"
monthly_cron = "0 0 9 25 * ?"
timezone = "Australia/Perth"
existing_cluster_id = ""

INSTALLER_BUILD = "2026-09-08-production-v7"
DASHBOARD_BUILD = "2026-09-08-simulator-v4"
DASHBOARD_NAME = "AuditHero - SCHADS Payroll Compliance"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Connect to the Databricks workspace
# MAGIC All installation actions use the identity executing this notebook.
# COMMAND ----------
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import zipfile

import requests
import yaml
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
api = w.api_client
me = w.current_user.me()
accounts_email = getattr(me, "user_name", None) or getattr(me, "userName", None) or ""

print(f"User: {accounts_email}")
print(f"Workspace: {w.config.host}")
print(f"Release: {release_ref}")
print(f"Installer build: {INSTALLER_BUILD}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Download and validate the selected release
# MAGIC The release archive is validated before workspace files or Jobs are changed.
# COMMAND ----------
archive_url = f"https://api.github.com/repos/disocodes/audithero/zipball/{release_ref}"
work_dir = Path(tempfile.mkdtemp(prefix="audithero-install-"))
archive_path = work_dir / "audithero.zip"

response = requests.get(archive_url, timeout=180)
response.raise_for_status()
archive_path.write_bytes(response.content)

with zipfile.ZipFile(archive_path) as zf:
    zf.extractall(work_dir / "source")

roots = [path for path in (work_dir / "source").iterdir() if path.is_dir()]
if len(roots) != 1:
    raise RuntimeError("AuditHero release archive did not contain one repository root.")
repo_root = roots[0]

required_release_files = [
    "notebooks/00_setup.py",
    "notebooks/00c_setup_genie.py",
    "notebooks/00d_verify_dashboard.py",
    "notebooks/00e_setup_investigation_view.py",
    "notebooks/00f_setup_pay_simulation.py",
    "notebooks/00g_setup_pay_review_master.py",
    "notebooks/01b_self_test.py",
    "notebooks/02f_auto_intake.py",
    "dashboard/payroll_compliance.spec.json",
    "dashboard/lakeview_builder.py",
    "dashboard/dashboard_enhancements.py",
    "dashboard/pay_simulation_dashboard.py",
    "dashboard/live_pay_simulator.py",
    "dashboard/live_pay_simulator_finalize.py",
    "dashboard/dashboard_layout_finalize.py",
    "resources/jobs.yml",
]
missing_release_files = [name for name in required_release_files if not (repo_root / name).exists()]
if missing_release_files:
    raise RuntimeError(
        "Selected AuditHero release is incomplete: " + ", ".join(missing_release_files)
    )
print(f"Release downloaded and validated: {repo_root.name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Workspace API helpers
# MAGIC Defines reusable helpers for workspace imports, dashboard discovery and module loading.
# COMMAND ----------
def call(method: str, path: str, body=None, query=None):
    return api.do(method, path, body=body, query=query)


def mkdirs(path: str):
    call("POST", "/api/2.0/workspace/mkdirs", {"path": path})


def import_file(local_path: Path, workspace_path: str, notebook: bool = False):
    body = {
        "path": workspace_path,
        "format": "SOURCE" if notebook else "RAW",
        "content": base64.b64encode(local_path.read_bytes()).decode("ascii"),
        "overwrite": True,
    }
    if notebook:
        body["language"] = "PYTHON"
    call("POST", "/api/2.0/workspace/import", body)


def list_dashboards():
    rows = []
    token = None
    while True:
        query = {"page_size": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.0/lakeview/dashboards", query=query) or {}
        rows.extend(payload.get("dashboards", []) or payload.get("value", []) or [])
        token = payload.get("next_page_token") or payload.get("nextPageToken")
        if not token:
            return rows


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load AuditHero module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value):
    if isinstance(value, str):
        value = json.loads(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


mkdirs(install_root)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Install or upgrade workspace files
# MAGIC Imports application source, Award rules, configuration, dashboard definitions, executable notebooks and administration notebooks under `/Shared/AuditHero`.
# COMMAND ----------
for name in ("databricks.yml", "pyproject.toml", "README.md"):
    path = repo_root / name
    if path.exists():
        import_file(path, f"{install_root}/{name}")

for directory in ("src", "rules", "config", "dashboard"):
    base = repo_root / directory
    if not base.exists():
        continue
    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(repo_root).as_posix()
        destination = f"{install_root}/{relative}"
        mkdirs(str(Path(destination).parent).replace("\\", "/"))
        import_file(file_path, destination)

mkdirs(f"{install_root}/notebooks")
for file_path in sorted((repo_root / "notebooks").glob("*.py")):
    destination_name = file_path.name if file_path.name == "_common.py" else file_path.stem
    import_file(
        file_path,
        f"{install_root}/notebooks/{destination_name}",
        notebook=file_path.name != "_common.py",
    )

mkdirs(f"{install_root}/admin")
import_file(
    repo_root / "installers" / "Databricks_Install_AuditHero.py",
    f"{install_root}/admin/AuditHero - Install or Upgrade",
    notebook=True,
)
import_file(
    repo_root / "installers" / "Databricks_Uninstall_AuditHero.py",
    f"{install_root}/admin/AuditHero - Uninstall",
    notebook=True,
)
print("Workspace files and notebooks installed/upgraded.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. Resolve the SQL warehouse
# MAGIC Reuses a configured or existing warehouse. If none exists and automatic creation is enabled, creates `AuditHero SQL Warehouse`.
# COMMAND ----------
def warehouses():
    return (call("GET", "/api/2.0/sql/warehouses") or {}).get("warehouses", []) or []


def resolve_warehouse(requested: str):
    if requested.strip():
        return requested.strip(), False

    available = warehouses()
    preferred = next((item for item in available if item.get("name") == "AuditHero SQL Warehouse"), None)
    selected = (
        preferred
        or next((item for item in available if item.get("state") == "RUNNING"), None)
        or (available[0] if available else None)
    )
    if selected:
        return selected["id"], False

    if not create_sql_warehouse_if_missing:
        raise RuntimeError("No SQL warehouse is available. Configure sql_warehouse_id and rerun the installer.")

    created = call(
        "POST",
        "/api/2.0/sql/warehouses",
        {
            "name": "AuditHero SQL Warehouse",
            "cluster_size": "2X-Small",
            "min_num_clusters": 1,
            "max_num_clusters": 1,
            "auto_stop_mins": 10,
            "enable_photon": True,
            "warehouse_type": "PRO",
            "enable_serverless_compute": True,
        },
    )
    return created["id"], True


warehouse_id, warehouse_created_by_installer = resolve_warehouse(sql_warehouse_id)
print(f"SQL warehouse: {warehouse_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 8. Resolve the managed dashboard
# MAGIC Reuses the existing AuditHero dashboard when present. On first installation, creates a base dashboard so dependent Job definitions have a dashboard resource ID. The enhanced definition is published in the dashboard deployment phase.
# COMMAND ----------
dashboard_matches = [item for item in list_dashboards() if item.get("display_name") == DASHBOARD_NAME]
if dashboard_matches:
    dashboard_id = dashboard_matches[0]["dashboard_id"]
    print(f"Using existing dashboard ID: {dashboard_id}")
else:
    placeholder_builder = load_module(
        "audithero_placeholder_builder",
        repo_root / "dashboard" / "lakeview_builder.py",
    )
    base_spec = json.loads(
        (repo_root / "dashboard" / "payroll_compliance.spec.json").read_text(encoding="utf-8")
    )
    created = call(
        "POST",
        "/api/2.0/lakeview/dashboards",
        {
            "display_name": DASHBOARD_NAME,
            "warehouse_id": warehouse_id,
            "serialized_dashboard": placeholder_builder.build_dashboard_text(base_spec),
            "parent_path": install_root,
        },
        query={"dataset_catalog": catalog, "dataset_schema": "gold"},
    )
    dashboard_id = created["dashboard_id"]
    call(
        "POST",
        f"/api/2.0/lakeview/dashboards/{dashboard_id}/published",
        {"embed_credentials": False, "warehouse_id": warehouse_id},
     )
    print(f"Created first-install dashboard: {dashboard_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 9. Create or update AuditHero Jobs
# MAGIC Applies the production Job definitions from `resources/jobs.yml`. Existing AuditHero Jobs are updated in place; missing Jobs are created.
# COMMAND ----------