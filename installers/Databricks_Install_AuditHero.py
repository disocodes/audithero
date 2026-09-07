# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Install or Upgrade
# MAGIC
# MAGIC Import this notebook into the Databricks workspace where AuditHero is installed and choose **Run all**. The notebook downloads the selected AuditHero release, updates workspace files and Jobs, runs Setup/Self Test, then builds, publishes and verifies the fully enhanced AI/BI dashboard from that exact downloaded release.
# MAGIC
# MAGIC Employment Hero credentials are optional and are not required for installation or uploaded CSV/Excel audits.

# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20" "pyyaml>=6.0" "requests>=2.32"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Installation settings
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

INSTALLER_BUILD = "2026-09-08-dashboard-v3"
DASHBOARD_NAME = "AuditHero - SCHADS Payroll Compliance"

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
print(f"Installing AuditHero as: {accounts_email}")
print(f"Workspace: {w.config.host}")
print(f"Release: {release_ref}")
print(f"Installer build: {INSTALLER_BUILD}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Download the AuditHero release
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

required_release_files = [
    repo_root / "dashboard" / "payroll_compliance.spec.json",
    repo_root / "dashboard" / "lakeview_builder.py",
    repo_root / "dashboard" / "dashboard_enhancements.py",
    repo_root / "dashboard" / "pay_simulation_dashboard.py",
    repo_root / "dashboard" / "live_pay_simulator.py",
    repo_root / "dashboard" / "live_pay_simulator_finalize.py",
    repo_root / "dashboard" / "dashboard_layout_finalize.py",
    repo_root / "notebooks" / "00d_verify_dashboard.py",
    repo_root / "notebooks" / "00f_setup_pay_simulation.py",
    repo_root / "notebooks" / "00g_setup_pay_review_master.py",
    repo_root / "notebooks" / "02f_auto_intake.py",
    repo_root / "resources" / "jobs.yml",
]
missing_release_files = [str(p.relative_to(repo_root)) for p in required_release_files if not p.exists()]
if missing_release_files:
    raise RuntimeError("The selected AuditHero release is incomplete: " + ", ".join(missing_release_files))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Workspace access
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


def _load_module(name: str, path: Path):
    module_spec = importlib.util.spec_from_file_location(name, path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"AuditHero module could not be loaded: {path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def canonical(value):
    if isinstance(value, str):
        value = json.loads(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


mkdirs(install_root)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Install AuditHero workspace files and notebooks
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
print("AuditHero workspace files and administration notebooks installed from the downloaded release.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Select the SQL warehouse
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
# MAGIC ## Resolve the managed dashboard ID without downgrading an existing dashboard
# MAGIC
# MAGIC Existing AuditHero dashboards are deliberately left untouched here. The complete enhanced definition is published only after Setup has created the simulation/reporting views.
# COMMAND ----------
existing_matches = [d for d in list_dashboards() if d.get("display_name") == DASHBOARD_NAME]
if existing_matches:
    dashboard_id = existing_matches[0]["dashboard_id"]
    print(f"Using existing AuditHero dashboard ID: {dashboard_id}")
    if len(existing_matches) > 1:
        print(f"Detected {len(existing_matches)} dashboards with the managed name; final verification will update all of them.")
else:
    builder = _load_module("audithero_placeholder_builder", repo_root / "dashboard" / "lakeview_builder.py")
    base_spec = json.loads((repo_root / "dashboard" / "payroll_compliance.spec.json").read_text(encoding="utf-8"))
    placeholder_text = builder.build_dashboard_text(base_spec)
    created = call(
        "POST",
        "/api/2.0/lakeview/dashboards",
        {
            "display_name": DASHBOARD_NAME,
            "warehouse_id": warehouse_id,
            "serialized_dashboard": placeholder_text,
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
    print(f"Created first-install placeholder dashboard: {dashboard_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Create or update AuditHero Jobs
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


legacy_job_names = {
    "AuditHero - Build Source Mapping Workbook (Advanced)": "AuditHero - Build Source Mapping Workbook",
    "AuditHero - Convert Source Files (Advanced)": "AuditHero - Convert Source Files",
    "AuditHero - Convert Mapped Files and Run Audit (Advanced)": "AuditHero - Convert Mapped Files and Run Audit",
    "AuditHero - File Readiness (Advanced)": "AuditHero - File Readiness",
    "AuditHero - Audit Canonical CSV Excel (Advanced)": "AuditHero - Audit Uploaded CSV Excel",
}
existing_jobs = list_jobs()
existing_by_name = {j.get("settings", {}).get("name"): j for j in existing_jobs}
installed_jobs = {}
for resource_key, raw_settings in job_defs.items():
    settings = resolve(raw_settings)
    name = settings["name"]
    existing = existing_by_name.get(name)
    if existing is None and name in legacy_job_names:
        existing = existing_by_name.get(legacy_job_names[name])
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
            return run_id
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for {label}.")


setup_run_id = run_job_and_wait(installed_jobs["setup"], "AuditHero Setup")
self_test_run_id = run_job_and_wait(installed_jobs["self_test"], "AuditHero Self Test")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Enforce the fully enhanced dashboard from this exact downloaded release
# MAGIC
# MAGIC This is intentionally duplicated with the Setup dashboard verifier. It prevents an installation from reporting success if Setup used a stale workspace copy or if multiple dashboards with the same name exist.
# COMMAND ----------
required_views = [
    "v_pay_review_employee_master",
    "v_pay_simulation_terms_latest",
    "v_pay_simulation_employee_year",
]
missing_views = []
for view in required_views:
    try:
        spark.sql(f"SELECT 1 FROM `{catalog}`.`gold`.`{view}` LIMIT 1").collect()
    except Exception:
        missing_views.append(f"{catalog}.gold.{view}")
if missing_views:
    raise RuntimeError(
        "AuditHero Setup completed but required pay-simulation views are missing: " + ", ".join(missing_views)
    )

builder = _load_module("audithero_release_builder", repo_root / "dashboard" / "lakeview_builder.py")
enhancements = _load_module("audithero_release_enhancements", repo_root / "dashboard" / "dashboard_enhancements.py")
pay_review = _load_module("audithero_release_pay_review", repo_root / "dashboard" / "pay_simulation_dashboard.py")
simulator = _load_module("audithero_release_simulator", repo_root / "dashboard" / "live_pay_simulator.py")
finalizer = _load_module("audithero_release_finalizer", repo_root / "dashboard" / "live_pay_simulator_finalize.py")

final_spec = json.loads((repo_root / "dashboard" / "payroll_compliance.spec.json").read_text(encoding="utf-8"))
final_spec = enhancements.enhance_spec(final_spec)
final_spec = pay_review.enhance_spec(final_spec)
final_spec = simulator.enhance_spec(final_spec)
final_spec = finalizer.enhance_spec(final_spec)
final_json = builder.build_dashboard(final_spec)
final_text = json.dumps(final_json, separators=(",", ":"))

all_layout = [item for page in final_json.get("pages", []) for item in page.get("layout", [])]
widget_names = {item.get("widget", {}).get("name") for item in all_layout}
required_widgets = {
    "live_sim_title",
    "sim_year",
    "sim_scenario",
    "sim_exact_rate",
    "sim_pay_model",
    "sim_total",
    "sim_variance",
    "sim_summary_heading",
    "sim_pay_outcomes_heading",
    "sim_shift_calculations_heading",
    "sim_award_components_heading",
    "sim_shift_table",
    "sim_component_table",
}
missing_widgets = sorted(required_widgets - widget_names)
if missing_widgets:
    raise RuntimeError("Downloaded release produced an incomplete simulator dashboard: " + ", ".join(missing_widgets))

employee_page = next((p for p in final_json.get("pages", []) if p.get("name") == "employee_deep_dive"), None)
if employee_page is None:
    raise RuntimeError("Downloaded release produced no Employee Deep Dive page")
page_extent = max(
    (item.get("position", {}).get("x", 0) + item.get("position", {}).get("width", 0) for item in employee_page.get("layout", [])),
    default=0,
)
if page_extent < 12:
    raise RuntimeError(f"Downloaded release dashboard is not full-width on the 12-column canvas; extent={page_extent}")

matches = [d for d in list_dashboards() if d.get("display_name") == DASHBOARD_NAME]
if not matches:
    raise RuntimeError("AuditHero dashboard disappeared during Setup")
if len(matches) > 1:
    print(f"Updating all {len(matches)} dashboards named '{DASHBOARD_NAME}' to eliminate stale duplicates.")

verified_dashboard_ids = []
for item in matches:
    target_id = item["dashboard_id"]
    current = call("GET", f"/api/2.0/lakeview/dashboards/{target_id}") or {}
    body = {
        "dashboard_id": target_id,
        "display_name": DASHBOARD_NAME,
        "warehouse_id": warehouse_id,
        "serialized_dashboard": final_text,
    }
    if current.get("etag"):
        body["etag"] = current["etag"]
    call(
        "PATCH",
        f"/api/2.0/lakeview/dashboards/{target_id}",
        body,
        query={"dataset_catalog": catalog, "dataset_schema": "gold"},
    )
    stored = call("GET", f"/api/2.0/lakeview/dashboards/{target_id}") or {}
    if canonical(stored.get("serialized_dashboard") or "{}") != canonical(final_text):
        raise RuntimeError(f"Databricks did not retain the enhanced dashboard definition for {target_id}")
    call(
        "POST",
        f"/api/2.0/lakeview/dashboards/{target_id}/published",
        {"embed_credentials": False, "warehouse_id": warehouse_id},
    )
    published = call("GET", f"/api/2.0/lakeview/dashboards/{target_id}/published") or {}
    if str(published.get("warehouse_id") or "") != warehouse_id:
        raise RuntimeError(f"Dashboard {target_id} published with an unexpected warehouse")
    verified_dashboard_ids.append(target_id)
    print(
        f"Enhanced dashboard verified: {target_id}; installer_build={INSTALLER_BUILD}; "
        f"revision={published.get('revision_create_time')}"
    )

dashboard_id = verified_dashboard_ids[0]

# COMMAND ----------
# MAGIC %md
# MAGIC ## Save installation state
# COMMAND ----------
state = {
    "release_ref": release_ref,
    "installer_build": INSTALLER_BUILD,
    "catalog": catalog,
    "install_root": install_root,
    "warehouse_id": warehouse_id,
    "warehouse_created_by_installer": warehouse_created_by_installer,
    "dashboard_id": dashboard_id,
    "dashboard_ids_verified": verified_dashboard_ids,
    "setup_run_id": setup_run_id,
    "self_test_run_id": self_test_run_id,
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
print(f"Verified enhanced dashboard ID(s): {', '.join(verified_dashboard_ids)}")
print("Expected dashboard: Employee Deep Dive begins with Roster Pay Simulator and uses the full 12-column canvas.")
print("Primary uploaded-file workflow:")
print("  1. Upload ordinary CSV/XLSX files to the raw import folder")
print("  2. Run AuditHero - Preview Uploaded Files")
print("  3. Review/confirm interpretation, then run AuditHero - Audit Reviewed Uploaded Files")
print("  4. Open AuditHero - SCHADS Payroll Compliance (AI/BI) or Genie")
print("Advanced import tools remain available for unusual source layouts.")
print("Employment Hero credentials are optional.")

# Remove an external bootstrap copy after successful first-time installation when
# the managed Install or Upgrade notebook is available.
try:
    context = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    current_path = context.notebookPath().get()
    managed_installer = f"{install_root}/admin/AuditHero - Install or Upgrade"
    if current_path and current_path != managed_installer and not current_path.startswith(f"{install_root}/"):
        call("POST", "/api/2.0/workspace/delete", {"path": current_path, "recursive": False})
except Exception as exc:
    print(f"Bootstrap notebook cleanup was not completed automatically: {exc}")
