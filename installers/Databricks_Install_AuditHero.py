# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Install or Upgrade
# MAGIC
# MAGIC Production installer and upgrader for AuditHero on Databricks.
# MAGIC
# MAGIC **Run all** performs these controlled phases:
# MAGIC 1. validate and import the selected AuditHero release;
# MAGIC 2. resolve shared Databricks resources;
# MAGIC 3. create or update AuditHero Jobs;
# MAGIC 4. run environment Setup;
# MAGIC 5. validate and publish the managed AI/BI dashboard;
# MAGIC 6. run the synthetic SCHADS calculation Self Test;
# MAGIC 7. record installation state.
# MAGIC
# MAGIC Setup, dashboard deployment and Self Test are separate execution phases. Each phase raises on failure so its status is unambiguous in Databricks.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Installer dependencies
# MAGIC Installs only the packages required by this installer to call Databricks APIs, download the selected release and parse the AuditHero resource manifest.
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

INSTALLER_BUILD = "2026-09-08-production-v8"
DASHBOARD_BUILD = "2026-09-08-simulator-v5"
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
# MAGIC The release archive is validated before workspace files or Jobs are changed. Required setup, dashboard, simulation, Self Test and Job definition files must all be present.
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
missing_release_files = [
    name for name in required_release_files if not (repo_root / name).exists()
]
if missing_release_files:
    raise RuntimeError(
        "Selected AuditHero release is incomplete: " + ", ".join(missing_release_files)
    )
print(f"Release downloaded and validated: {repo_root.name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Workspace API helpers
# MAGIC Defines reusable helpers for workspace imports, Job execution, dashboard discovery and dashboard semantic validation.
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


def parse_serialized_dashboard(value):
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return value
    raise TypeError(f"Unexpected serialized dashboard type: {type(value).__name__}")


def dashboard_widget_names(document: dict) -> set[str]:
    return {
        item.get("widget", {}).get("name")
        for page in document.get("pages", [])
        for item in page.get("layout", [])
        if item.get("widget", {}).get("name")
    }


def dashboard_dataset_names(document: dict) -> set[str]:
    return {
        item.get("name")
        for item in document.get("datasets", [])
        if item.get("name")
    }


def dashboard_page_names(document: dict) -> set[str]:
    return {
        page.get("name")
        for page in document.get("pages", [])
        if page.get("name")
    }


def employee_deep_dive_extent(document: dict) -> int:
    page = next(
        (item for item in document.get("pages", []) if item.get("name") == "employee_deep_dive"),
        None,
    )
    if page is None:
        return 0
    return max(
        (
            item.get("position", {}).get("x", 0)
            + item.get("position", {}).get("width", 0)
            for item in page.get("layout", [])
        ),
        default=0,
    )


mkdirs(install_root)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Install or upgrade workspace files
# MAGIC Imports application source, Award rules, configuration, dashboard definitions, executable notebooks and administration notebooks under `/Shared/AuditHero`. Existing files are upgraded in place.
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
    preferred = next(
        (item for item in available if item.get("name") == "AuditHero SQL Warehouse"),
        None,
    )
    selected = (
        preferred
        or next((item for item in available if item.get("state") == "RUNNING"), None)
        or (available[0] if available else None)
    )
    if selected:
        return selected["id"], False

    if not create_sql_warehouse_if_missing:
        raise RuntimeError(
            "No SQL warehouse is available. Configure sql_warehouse_id and rerun the installer."
        )

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
# MAGIC Reuses the existing AuditHero dashboard when present. On first installation, creates a base dashboard so dependent Job definitions have a dashboard resource ID. The enhanced definition is published later.
# COMMAND ----------
dashboard_matches = [
    item for item in list_dashboards() if item.get("display_name") == DASHBOARD_NAME
]
if dashboard_matches:
    dashboard_id = dashboard_matches[0]["dashboard_id"]
    print(f"Using existing dashboard ID: {dashboard_id}")
else:
    placeholder_builder = load_module(
        "audithero_placeholder_builder",
        repo_root / "dashboard" / "lakeview_builder.py",
    )
    base_spec = json.loads(
        (repo_root / "dashboard" / "payroll_compliance.spec.json").read_text(
            encoding="utf-8"
        )
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
# MAGIC Applies the complete production Job definitions from `resources/jobs.yml`. Existing AuditHero Jobs are updated in place; missing Jobs are created.
# COMMAND ----------
jobs_doc = yaml.safe_load((repo_root / "resources" / "jobs.yml").read_text())
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


def resolve_resource(value):
    if isinstance(value, dict):
        result = {key: resolve_resource(item) for key, item in value.items()}
        if (
            existing_cluster_id
            and "notebook_task" in result
            and "existing_cluster_id" not in result
        ):
            result["existing_cluster_id"] = existing_cluster_id
        return result
    if isinstance(value, list):
        return [resolve_resource(item) for item in value]
    if not isinstance(value, str):
        return value
    if value.startswith("../notebooks/"):
        return f"{install_root}/notebooks/{Path(value).stem}"
    for source, target in replacements.items():
        value = value.replace(source, str(target))
    return value


def list_jobs():
    rows = []
    token = None
    while True:
        query = {"limit": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.2/jobs/list", query=query) or {}
        rows.extend(payload.get("jobs", []) or [])
        token = payload.get("next_page_token")
        if not token:
            return rows


existing_by_name = {
    item.get("settings", {}).get("name"): item for item in list_jobs()
}
installed_jobs = {}
legacy_job_names = {
    "AuditHero - Build Source Mapping Workbook (Advanced)": "AuditHero - Build Source Mapping Workbook",
    "AuditHero - Convert Source Files (Advanced)": "AuditHero - Convert Source Files",
    "AuditHero - Convert Mapped Files and Run Audit (Advanced)": "AuditHero - Convert Mapped Files and Run Audit",
    "AuditHero - File Readiness (Advanced)": "AuditHero - File Readiness",
    "AuditHero - Audit Canonical CSV Excel (Advanced)": "AuditHero - Audit Uploaded CSV Excel",
}

for resource_key, raw_settings in job_defs.items():
    settings = resolve_resource(raw_settings)
    name = settings["name"]
    existing = existing_by_name.get(name) or existing_by_name.get(
        legacy_job_names.get(name, "")
    )
    if existing:
        call(
            "POST",
            "/api/2.2/jobs/reset",
            {"job_id": existing["job_id"], "new_settings": settings},
        )
        job_id = existing["job_id"]
        print(f"Updated job: {name}")
    else:
        job_id = call("POST", "/api/2.2/jobs/create", settings)["job_id"]
        print(f"Created job: {name}")
    installed_jobs[resource_key] = job_id

# COMMAND ----------
# MAGIC %md
# MAGIC ## 10. Job execution and diagnostics
# MAGIC Defines execution helpers used by Setup and Self Test. Failed tasks are separated from downstream tasks blocked by dependency failure.
# COMMAND ----------
def get_run(run_id):
    return call("GET", "/api/2.2/jobs/runs/get", query={"run_id": run_id}) or {}


def run_output(run_id):
    for version in ("2.2", "2.1"):
        try:
            return call(
                "GET",
                f"/api/{version}/jobs/runs/get-output",
                query={"run_id": run_id},
            ) or {}
        except Exception:
            pass
    return {}


def diagnostics(parent_id):
    tasks = get_run(parent_id).get("tasks", []) or []
    failed = []
    blocked = []

    for task in tasks:
        state = task.get("state", {}) or {}
        result = state.get("result_state")
        lifecycle = state.get("life_cycle_state")
        if result == "SUCCESS":
            continue
        if lifecycle == "SKIPPED" or result == "UPSTREAM_FAILED":
            blocked.append((task, state))
        else:
            failed.append((task, state))

    for heading, rows in (("FAILED TASK", failed), ("BLOCKED TASK", blocked)):
        for task, state in rows:
            key = task.get("task_key", "unknown")
            task_run_id = task.get("run_id")
            print(
                f"\n{heading}: {key} | run={task_run_id} | "
                f"lifecycle={state.get('life_cycle_state')} | "
                f"result={state.get('result_state')}"
            )
            if state.get("state_message"):
                print("  " + state["state_message"])
            if task_run_id and heading == "FAILED TASK":
                output = run_output(task_run_id)
                text = (
                    output.get("error")
                    or output.get("error_trace")
                    or (output.get("notebook_output") or {}).get("result")
                )
                if text:
                    print(str(text)[:12000])

    return {
        "failed_tasks": [task.get("task_key", "unknown") for task, _ in failed],
        "blocked_tasks": [task.get("task_key", "unknown") for task, _ in blocked],
    }


def run_job(job_id, label, timeout=3600):
    run_id = call("POST", "/api/2.2/jobs/run-now", {"job_id": job_id})["run_id"]
    print(f"Started {label}: run {run_id}")
    deadline = time.time() + timeout

    while time.time() < deadline:
        state = get_run(run_id).get("state", {}) or {}
        lifecycle = state.get("life_cycle_state")
        result = state.get("result_state")
        if lifecycle in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
            ok = result == "SUCCESS"
            diagnostic = (
                {"failed_tasks": [], "blocked_tasks": []}
                if ok
                else diagnostics(run_id)
            )
            payload = {
                "ok": ok,
                "run_id": run_id,
                "lifecycle": lifecycle,
                "result": result,
                "message": state.get("state_message") or "",
                **diagnostic,
            }
            print(f"{label}: {'SUCCESS' if ok else 'FAILED'}")
            return payload
        time.sleep(10)

    return {
        "ok": False,
        "run_id": run_id,
        "lifecycle": "TIMEOUT",
        "result": None,
        "message": f"Timed out after {timeout}s",
        "failed_tasks": [],
        "blocked_tasks": [],
    }


def require_success(result, label):
    if result["ok"]:
        return
    root = ", ".join(result.get("failed_tasks") or []) or "unknown task"
    blocked = ", ".join(result.get("blocked_tasks") or [])
    detail = f"; blocked downstream tasks: {blocked}" if blocked else ""
    raise RuntimeError(
        f"{label} failed. Root failed task(s): {root}{detail}. "
        f"Open Databricks Job run {result['run_id']} for full task output."
    )

# COMMAND ----------
# MAGIC %md
# MAGIC ## 11. Run AuditHero environment Setup
# MAGIC Setup prepares the governed AuditHero environment. Its Job contains independent tasks for core catalog/table/rule setup, Genie, investigation views, roster simulation, employee review master and dashboard-definition validation.
# MAGIC
# MAGIC Setup does not run an employee payroll audit and does not execute the calculation Self Test.
# COMMAND ----------
setup_result = run_job(installed_jobs["setup"], "AuditHero Setup")
setup_run_id = setup_result["run_id"]
require_success(setup_result, "AuditHero Setup")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 12. Dashboard data preflight
# MAGIC Confirms the governed views required by the managed AI/BI dashboard are queryable before dashboard publication.
# COMMAND ----------
view_names = [
    "v_audit_investigation_latest",
    "v_award_scenario_detail_latest",
    "v_award_criteria_detail_latest",
    "v_award_scenario_rest_findings_latest",
    "v_reconciliation_latest",
    "v_audit_runs",
    "v_readiness_findings",
    "v_rule_coverage",
    "v_pay_review_employee_master",
    "v_pay_simulation_terms_latest",
    "v_pay_simulation_employee_year",
]

dashboard_missing_views = []
for view_name in view_names:
    try:
        spark.sql(
            f"SELECT 1 FROM `{catalog}`.`gold`.`{view_name}` LIMIT 1"
        ).collect()
    except Exception as exc:
        dashboard_missing_views.append(
            (f"{catalog}.gold.{view_name}", str(exc))
        )

if dashboard_missing_views:
    print("Dashboard preflight FAILED:")
    for object_name, error in dashboard_missing_views:
        print(f"  - {object_name}: {error[:1000]}")
    raise RuntimeError(
        "AuditHero dashboard preflight failed; required governed views are missing or not queryable: "
        + ", ".join(name for name, _ in dashboard_missing_views)
    )

print("Dashboard preflight PASSED: all required views are queryable.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 13. Build, publish and verify the enhanced AI/BI dashboard
# MAGIC Builds the version-controlled dashboard definition, applies the roster-pay simulator and 12-column layout, updates the managed dashboard, then verifies the stored dashboard semantically.
# MAGIC
# MAGIC Databricks may normalize serialized dashboard JSON during persistence. Verification therefore checks required pages, datasets, simulator widgets and full-width layout instead of requiring exact JSON serialization equality.
# COMMAND ----------
verified_dashboard_ids = []
dashboard_result = {"ok": False, "status": "NOT_RUN", "message": ""}

try:
    builder = load_module(
        "audithero_dashboard_builder",
        repo_root / "dashboard" / "lakeview_builder.py",
    )
    enhancements = load_module(
        "audithero_dashboard_enhancements",
        repo_root / "dashboard" / "dashboard_enhancements.py",
    )
    pay_layer = load_module(
        "audithero_pay_simulation_dashboard",
        repo_root / "dashboard" / "pay_simulation_dashboard.py",
    )
    live_layer = load_module(
        "audithero_live_pay_simulator",
        repo_root / "dashboard" / "live_pay_simulator.py",
    )
    finalizer = load_module(
        "audithero_live_pay_simulator_finalize",
        repo_root / "dashboard" / "live_pay_simulator_finalize.py",
    )

    dashboard_spec = json.loads(
        (repo_root / "dashboard" / "payroll_compliance.spec.json").read_text(
            encoding="utf-8"
        )
    )
    dashboard_spec = enhancements.enhance_spec(dashboard_spec)
    dashboard_spec = pay_layer.enhance_spec(dashboard_spec)
    dashboard_spec = live_layer.enhance_spec(dashboard_spec)
    dashboard_spec = finalizer.enhance_spec(dashboard_spec)

    final_json = builder.build_dashboard(dashboard_spec)
    final_text = json.dumps(final_json, separators=(",", ":"))

    required_widgets = {
        "live_sim_title",
        "sim_year",
        "sim_scenario",
        "sim_exact_rate",
        "sim_pay_model",
        "sim_selected_rate_kpi",
        "sim_total",
        "sim_variance",
        "sim_summary_heading",
        "sim_pay_outcomes_heading",
        "sim_shift_calculations_heading",
        "sim_award_components_heading",
        "sim_shift_table",
        "sim_component_table",
    }
    required_datasets = {
        "pay_rate_choices",
        "pay_model_choices",
        "pay_sim_live",
        "pay_sim_shift_live",
        "pay_sim_components_live",
        "pay_rate_position",
    }
    required_pages = {
        "audit_overview",
        "employee_deep_dive",
        "audit_components",
    }

    expected_pages = dashboard_page_names(final_json)
    expected_widgets = dashboard_widget_names(final_json)
    expected_datasets = dashboard_dataset_names(final_json)

    missing_widgets = sorted(required_widgets - expected_widgets)
    if missing_widgets:
        raise RuntimeError(
            "Generated dashboard is missing required simulator widgets: "
            + ", ".join(missing_widgets)
        )

    missing_datasets = sorted(required_datasets - expected_datasets)
    if missing_datasets:
        raise RuntimeError(
            "Generated dashboard is missing required simulator datasets: "
            + ", ".join(missing_datasets)
        )

    missing_pages = sorted(required_pages - expected_pages)
    if missing_pages:
        raise RuntimeError(
            "Generated dashboard is missing required pages: "
            + ", ".join(missing_pages)
        )

    generated_extent = employee_deep_dive_extent(final_json)
    if generated_extent < 12:
        raise RuntimeError(
            f"Generated Employee Deep Dive is not full-width; extent={generated_extent}"
        )

    targets = [
        item for item in list_dashboards() if item.get("display_name") == DASHBOARD_NAME
    ]
    if not targets:
        raise RuntimeError("Managed AuditHero dashboard was not found.")

    def stored_dashboard_errors(document: dict) -> list[str]:
        errors = []
        stored_pages = dashboard_page_names(document)
        stored_widgets = dashboard_widget_names(document)
        stored_datasets = dashboard_dataset_names(document)

        if stored_pages != expected_pages:
            missing = sorted(expected_pages - stored_pages)
            extra = sorted(stored_pages - expected_pages)
            errors.append(
                f"page set differs (missing={missing or 'none'}, extra={extra or 'none'})"
            )

        missing = sorted(required_widgets - stored_widgets)
        if missing:
            errors.append("missing simulator widgets: " + ", ".join(missing))

        missing = sorted(required_datasets - stored_datasets)
        if missing:
            errors.append("missing simulator datasets: " + ", ".join(missing))

        extent = employee_deep_dive_extent(document)
        if extent < 12:
            errors.append(f"Employee Deep Dive extent is {extent}, expected at least 12")

        return errors

    for dashboard in targets:
        target_id = dashboard["dashboard_id"]
        current = call(
            "GET", f"/api/2.0/lakeview/dashboards/{target_id}"
        ) or {}
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

        verification_deadline = time.time() + 30
        last_errors = ["dashboard definition was not yet readable"]
        while time.time() < verification_deadline:
            stored = call(
                "GET", f"/api/2.0/lakeview/dashboards/{target_id}"
            ) or {}
            try:
                stored_document = parse_serialized_dashboard(
                    stored.get("serialized_dashboard")
                )
                last_errors = stored_dashboard_errors(stored_document)
            except Exception as exc:
                last_errors = [f"stored dashboard could not be parsed: {exc}"]

            if not last_errors:
                break
            time.sleep(2)

        if last_errors:
            raise RuntimeError(
                f"Stored dashboard {target_id} failed semantic verification: "
                + " | ".join(last_errors)
            )

        call(
            "POST",
            f"/api/2.0/lakeview/dashboards/{target_id}/published",
            {"embed_credentials": False, "warehouse_id": warehouse_id},
        )
        verified_dashboard_ids.append(target_id)
        print(
            f"Enhanced dashboard verified and published: {target_id}; "
            f"dashboard_build={DASHBOARD_BUILD}"
        )

    dashboard_id = verified_dashboard_ids[0]
    dashboard_result = {
        "ok": True,
        "status": "SUCCESS",
        "message": f"Verified {len(verified_dashboard_ids)} dashboard(s)",
    }

except Exception as exc:
    dashboard_result = {
        "ok": False,
        "status": "FAILED",
        "message": str(exc),
    }
    print("Dashboard deployment FAILED:\n" + str(exc))
    raise RuntimeError("AuditHero dashboard deployment failed: " + str(exc)) from exc

# COMMAND ----------
# MAGIC %md
# MAGIC ## 14. Deployment checkpoint
# MAGIC Reports successful completion of the environment and dashboard phases before running the independent calculation Self Test.
# COMMAND ----------
print(f"Setup: PASS (run {setup_run_id})")
print(
    f"Dashboard: PASS ({dashboard_result['status']}) — "
    f"{dashboard_result.get('message', '')}"
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 15. Run AuditHero Self Test
# MAGIC Self Test uses synthetic data only; it does not read employee or payroll files.
# MAGIC
# MAGIC It validates deterministic calculation-engine behaviour for:
# MAGIC 1. SCHADS rule-library integrity and effective-dated reference rates;
# MAGIC 2. a known casual Saturday penalty calculation;
# MAGIC 3. sleepover treatment and allowance evidence;
# MAGIC 4. local public-holiday location scoping;
# MAGIC 5. broken-shift grouping and allowance evidence;
# MAGIC 6. weekly/period overtime allocation and repricing.
# MAGIC
# MAGIC Self Test does not test Employment Hero connectivity, uploaded-file quality, dashboard permissions or compliance of any real employee.
# COMMAND ----------
self_test_result = run_job(installed_jobs["self_test"], "AuditHero Self Test")
self_test_run_id = self_test_result["run_id"]
require_success(self_test_result, "AuditHero Self Test")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 16. Save installation report and final status
# MAGIC Reached after Setup, dashboard deployment and Self Test have succeeded. Saves release/resource IDs and phase results to `/Shared/AuditHero/install_state.json`.
# COMMAND ----------
state = {
    "release_ref": release_ref,
    "installer_build": INSTALLER_BUILD,
    "dashboard_build": DASHBOARD_BUILD,
    "catalog": catalog,
    "install_root": install_root,
    "warehouse_id": warehouse_id,
    "warehouse_created_by_installer": warehouse_created_by_installer,
    "dashboard_id": dashboard_id,
    "dashboard_ids_verified": verified_dashboard_ids,
    "setup": setup_result,
    "dashboard": dashboard_result,
    "self_test": self_test_result,
    "setup_run_id": setup_run_id,
    "self_test_run_id": self_test_run_id,
    "jobs": installed_jobs,
    "installed_by": accounts_email,
}

call(
    "POST",
    "/api/2.0/workspace/import",
    {
        "path": f"{install_root}/install_state.json",
        "format": "RAW",
        "content": base64.b64encode(
            json.dumps(state, indent=2).encode("utf-8")
        ).decode("ascii"),
        "overwrite": True,
    },
)

print("\nAUDITHERO INSTALL / UPGRADE SUMMARY")
print("  Setup:     PASS")
print("  Dashboard: PASS")
print("  Self Test: PASS")
print("AuditHero installation completed successfully.")
print("Primary uploaded-file workflow:")
print("  1. Upload ordinary CSV/XLSX files to the raw import folder")
print("  2. Run AuditHero - Preview Uploaded Files")
print("  3. Review/confirm interpretation, then run AuditHero - Audit Reviewed Uploaded Files")
print("  4. Open AuditHero - SCHADS Payroll Compliance")
