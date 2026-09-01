# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Install or Upgrade
# MAGIC
# MAGIC Import this notebook into the Databricks workspace where AuditHero will be installed and choose **Run all**. The notebook downloads the selected AuditHero release, installs or updates AuditHero workspace files and Jobs, prepares the AI/BI reporting assets, and runs Setup and Self Test.
# MAGIC
# MAGIC Employment Hero credentials are optional and are not required for installation or uploaded CSV/Excel audits.

# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20" "pyyaml>=6.0" "requests>=2.32"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Installation settings
# MAGIC
# MAGIC Default settings target a Unity Catalog workspace with serverless Jobs enabled. `sql_warehouse_id` can remain blank; AuditHero uses an available SQL warehouse or creates **AuditHero SQL Warehouse** when permissions allow it.

# COMMAND ----------
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
secret_scope = "audithero"
monthly_cron = "0 0 9 25 * ?"
timezone = "Australia/Perth"

# Leave blank to use serverless compute for AuditHero notebook Jobs. If serverless
# Jobs are unavailable, enter a compatible existing cluster ID.
existing_cluster_id = ""

# COMMAND ----------
import base64
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
print(f"Installing AuditHero as: {accounts_email}")
print(f"Workspace: {w.config.host}")
print(f"Release: {release_ref}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Download the AuditHero release
# MAGIC
# MAGIC The selected public repository release is downloaded into temporary driver storage for installation.

# COMMAND ----------
archive_url = f"https://api.github.com/repos/disocodes/audithero/zipball/{release_ref}"
work_dir = Path(tempfile.mkdtemp(prefix="audithero-install-"))
archive_path = work_dir / "audithero.zip"
r = requests.get(archive_url, timeout=180)
r.raise_for_status()
archive_path.write_bytes(r.content)
with zipfile.ZipFile(archive_path) as zf:
    zf.extractall(work_dir / "source")
roots = [p for p in (work_dir / "source").iterdir() if p.is_dir()]
if len(roots) != 1:
    raise RuntimeError("The AuditHero release archive did not contain one repository root.")
repo_root = roots[0]
print(f"Release downloaded: {repo_root.name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Workspace access
# MAGIC
# MAGIC Installation uses the current Databricks notebook identity. A personal access token does not need to be entered in this notebook.

# COMMAND ----------
def call(method: str, path: str, body=None, query=None):
    return api.do(method, path, body=body, query=query)


def import_raw(local_path: Path, workspace_path: str):
    content = base64.b64encode(local_path.read_bytes()).decode("ascii")
    call("POST", "/api/2.0/workspace/import", {
        "path": workspace_path,
        "format": "RAW",
        "content": content,
        "overwrite": True,
    })


def import_notebook(local_path: Path, workspace_path: str):
    content = base64.b64encode(local_path.read_bytes()).decode("ascii")
    call("POST", "/api/2.0/workspace/import", {
        "path": workspace_path,
        "format": "SOURCE",
        "language": "PYTHON",
        "content": content,
        "overwrite": True,
    })


def mkdirs(path: str):
    call("POST", "/api/2.0/workspace/mkdirs", {"path": path})


mkdirs(install_root)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Install AuditHero workspace files and notebooks
# MAGIC
# MAGIC Audit notebooks are installed as runnable Databricks notebooks. Shared Python code, rule packs and configuration files are installed under `/Shared/AuditHero`. Managed administration notebooks are installed under `/Shared/AuditHero/admin`.

# COMMAND ----------
for name in ("databricks.yml", "pyproject.toml", "README.md"):
    path = repo_root / name
    if path.exists():
        import_raw(path, f"{install_root}/{name}")

for directory in ("src", "rules", "config", "dashboard"):
    base = repo_root / directory
    if not base.exists():
        continue
    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(repo_root).as_posix()
        dest = f"{install_root}/{rel}"
        mkdirs(str(Path(dest).parent).replace("\\", "/"))
        import_raw(file_path, dest)

notebook_dir = repo_root / "notebooks"
mkdirs(f"{install_root}/notebooks")
for file_path in sorted(notebook_dir.glob("*.py")):
    if file_path.name == "_common.py":
        import_raw(file_path, f"{install_root}/notebooks/_common.py")
    else:
        import_notebook(file_path, f"{install_root}/notebooks/{file_path.stem}")

mkdirs(f"{install_root}/admin")
import_notebook(
    repo_root / "installers" / "Databricks_Install_AuditHero.py",
    f"{install_root}/admin/AuditHero - Install or Upgrade",
)
import_notebook(
    repo_root / "installers" / "Databricks_Uninstall_AuditHero.py",
    f"{install_root}/admin/AuditHero - Uninstall",
)

print("AuditHero workspace files and administration notebooks installed.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Select the SQL warehouse
# MAGIC
# MAGIC AuditHero uses the configured warehouse ID when supplied. Otherwise it selects **AuditHero SQL Warehouse**, a running warehouse, or another available warehouse. If no warehouse exists and automatic creation is enabled, the installer creates one when permitted.

# COMMAND ----------
def list_warehouses():
    payload = call("GET", "/api/2.0/sql/warehouses") or {}
    return payload.get("warehouses", []) or []


def resolve_warehouse(requested: str):
    if requested.strip():
        return requested.strip(), False
    warehouses = list_warehouses()
    preferred = next((x for x in warehouses if x.get("name") == "AuditHero SQL Warehouse"), None)
    if preferred:
        return preferred["id"], False
    running = next((x for x in warehouses if x.get("state") == "RUNNING"), None)
    if running:
        return running["id"], False
    if warehouses:
        return warehouses[0]["id"], False
    if not create_sql_warehouse_if_missing:
        raise RuntimeError("No SQL warehouse is available. Create one or enter sql_warehouse_id and rerun the installer.")
    try:
        created = call("POST", "/api/2.0/sql/warehouses", {
            "name": "AuditHero SQL Warehouse",
            "cluster_size": "2X-Small",
            "min_num_clusters": 1,
            "max_num_clusters": 1,
            "auto_stop_mins": 10,
            "enable_photon": True,
            "warehouse_type": "PRO",
            "enable_serverless_compute": True,
        })
        return created["id"], True
    except Exception as exc:
        raise RuntimeError(
            "No SQL warehouse is available and AuditHero could not create one automatically. "
            "Create or select a SQL warehouse, enter its ID in sql_warehouse_id, and rerun the installer."
        ) from exc


warehouse_id, warehouse_created_by_installer = resolve_warehouse(sql_warehouse_id)
print(f"AuditHero SQL warehouse: {warehouse_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Create or update the AI/BI dashboard
# MAGIC
# MAGIC The dashboard is published with embedded credentials disabled and uses the selected AuditHero SQL warehouse.

# COMMAND ----------
dashboard_name = "AuditHero - SCHADS Payroll Compliance"
serialized_dashboard = (repo_root / "dashboard" / "payroll_compliance.lvdash.json").read_text(encoding="utf-8")


def list_dashboards():
    result = []
    token = None
    while True:
        query = {"page_size": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.0/lakeview/dashboards", query=query) or {}
        result.extend(payload.get("dashboards", []) or payload.get("value", []) or [])
        token = payload.get("next_page_token") or payload.get("nextPageToken")
        if not token:
            return result


existing_dashboard = next((d for d in list_dashboards() if d.get("display_name") == dashboard_name), None)
dashboard_body = {
    "display_name": dashboard_name,
    "warehouse_id": warehouse_id,
    "serialized_dashboard": serialized_dashboard,
    "parent_path": install_root,
}
if existing_dashboard:
    dashboard_body["dashboard_id"] = existing_dashboard["dashboard_id"]
    dashboard = call("PATCH", f"/api/2.0/lakeview/dashboards/{existing_dashboard['dashboard_id']}", dashboard_body)
else:
    dashboard = call(
        "POST",
        "/api/2.0/lakeview/dashboards",
        dashboard_body,
        query={"dataset_catalog": catalog, "dataset_schema": "gold"},
    )
dashboard_id = (dashboard or existing_dashboard)["dashboard_id"]
call(
    "POST",
    f"/api/2.0/lakeview/dashboards/{dashboard_id}/published",
    {"embed_credentials": False, "warehouse_id": warehouse_id},
)
print(f"AI/BI dashboard published: {dashboard_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Create or update AuditHero Jobs
# MAGIC
# MAGIC AuditHero Job definitions are loaded from `resources/jobs.yml`. Deployment variables and notebook paths are resolved for the installed workspace. Notebook tasks use serverless Jobs unless `existing_cluster_id` is configured.

# COMMAND ----------
jobs_doc = yaml.safe_load((repo_root / "resources" / "jobs.yml").read_text(encoding="utf-8"))
job_defs = jobs_doc["resources"]["jobs"]

replacements = {
    "${var.catalog}": catalog,
    "${var.secret_scope}": secret_scope,
    "${var.sql_warehouse_id}": warehouse_id,
    "${var.accounts_email}": accounts_email,
    "${var.monthly_cron}": monthly_cron,
    "${var.timezone}": timezone,
    "${resources.dashboards.payroll_compliance.id}": dashboard_id,
}


def resolve(value):
    if isinstance(value, dict):
        out = {k: resolve(v) for k, v in value.items()}
        if existing_cluster_id and "notebook_task" in out and "existing_cluster_id" not in out:
            out["existing_cluster_id"] = existing_cluster_id
        return out
    if isinstance(value, list):
        return [resolve(v) for v in value]
    if not isinstance(value, str):
        return value
    if value.startswith("../notebooks/"):
        return f"{install_root}/notebooks/{Path(value).stem}"
    for old, new in replacements.items():
        value = value.replace(old, str(new))
    return value


def list_jobs():
    jobs = []
    token = None
    while True:
        query = {"limit": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.2/jobs/list", query=query) or {}
        jobs.extend(payload.get("jobs", []) or [])
        token = payload.get("next_page_token")
        if not token:
            return jobs


existing_by_name = {j.get("settings", {}).get("name"): j for j in list_jobs()}
installed_jobs = {}
for resource_key, raw_settings in job_defs.items():
    settings = resolve(raw_settings)
    name = settings["name"]
    existing = existing_by_name.get(name)
    if existing:
        call("POST", "/api/2.2/jobs/reset", {"job_id": existing["job_id"], "new_settings": settings})
        job_id = existing["job_id"]
        print(f"Updated job: {name}")
    else:
        created = call("POST", "/api/2.2/jobs/create", settings)
        job_id = created["job_id"]
        print(f"Created job: {name}")
    installed_jobs[resource_key] = job_id

# COMMAND ----------
# MAGIC %md
# MAGIC ## Run Setup and Self Test
# MAGIC
# MAGIC Setup prepares the Unity Catalog structures, rule references, semantic metric views and Genie space. Self Test validates representative SCHADS calculations. Installation stops if either validation step fails.

# COMMAND ----------
def run_job_and_wait(job_id: int, label: str):
    run = call("POST", "/api/2.2/jobs/run-now", {"job_id": job_id})
    run_id = run["run_id"]
    print(f"Started {label}: run {run_id}")
    deadline = time.time() + 3600
    while time.time() < deadline:
        state = (call("GET", "/api/2.2/jobs/runs/get", query={"run_id": run_id}) or {}).get("state", {})
        lifecycle = state.get("life_cycle_state")
        result = state.get("result_state")
        if lifecycle in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
            if result != "SUCCESS":
                raise RuntimeError(f"{label} failed: lifecycle={lifecycle}, result={result}, message={state.get('state_message')}")
            print(f"{label}: SUCCESS")
            return
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for {label}.")


run_job_and_wait(installed_jobs["setup"], "AuditHero Setup")
run_job_and_wait(installed_jobs["self_test"], "AuditHero Self Test")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Save installation state
# MAGIC
# MAGIC Resource IDs and installation settings are saved for upgrades and uninstall.

# COMMAND ----------
state = {
    "release_ref": release_ref,
    "catalog": catalog,
    "install_root": install_root,
    "warehouse_id": warehouse_id,
    "warehouse_created_by_installer": warehouse_created_by_installer,
    "dashboard_id": dashboard_id,
    "jobs": installed_jobs,
    "installed_by": accounts_email,
}
state_bytes = json.dumps(state, indent=2).encode("utf-8")
call("POST", "/api/2.0/workspace/import", {
    "path": f"{install_root}/install_state.json",
    "format": "RAW",
    "content": base64.b64encode(state_bytes).decode("ascii"),
    "overwrite": True,
})

print("\nAuditHero installation completed successfully.")
print("For uploaded CSV/Excel audits, use:")
print("  • AuditHero - Build Source Mapping Workbook")
print("  • AuditHero - Convert Mapped Files and Run Audit")
print("  • AuditHero - Audit Uploaded CSV Excel")
print("Review results in:")
print("  • AuditHero - SCHADS Payroll Compliance (AI/BI)")
print("  • AuditHero - Payroll Compliance (Genie)")
print("Administration notebooks are installed under /Shared/AuditHero/admin:")
print("  • AuditHero - Install or Upgrade")
print("  • AuditHero - Uninstall")
print("Employment Hero credentials are optional.")

# Remove the imported bootstrap copy after successful first-time installation when
# the managed Install or Upgrade notebook is available.
try:
    context = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    current_path = context.notebookPath().get()
    managed_installer = f"{install_root}/admin/AuditHero - Install or Upgrade"
    if current_path and current_path != managed_installer and not current_path.startswith(f"{install_root}/"):
        call("POST", "/api/2.0/workspace/delete", {"path": current_path, "recursive": False})
except Exception as exc:
    print(f"Bootstrap notebook cleanup was not completed automatically: {exc}")
