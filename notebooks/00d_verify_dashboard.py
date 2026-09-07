# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Verify AI/BI Dashboard
# MAGIC
# MAGIC Build the complete AuditHero dashboard, including roster-pay simulation, from the version-controlled dashboard layers and ensure every AuditHero dashboard with the managed name is updated and published.
# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20"
# COMMAND ----------
from pathlib import Path
import importlib.util
import json

exec(open(str(Path.cwd() / "_common.py")).read())

from databricks.sdk import WorkspaceClient

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("sql_warehouse_id", "")

catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"
warehouse_id = dbutils.widgets.get("sql_warehouse_id").strip()
if not warehouse_id:
    raise ValueError("sql_warehouse_id is required to verify and publish the AuditHero dashboard")

DASHBOARD_NAME = "AuditHero - SCHADS Payroll Compliance"
DASHBOARD_BUILD = "2026-09-08-simulator-v3"

paths = {
    "spec": ROOT / "dashboard" / "payroll_compliance.spec.json",
    "builder": ROOT / "dashboard" / "lakeview_builder.py",
    "enhancements": ROOT / "dashboard" / "dashboard_enhancements.py",
    "pay_review": ROOT / "dashboard" / "pay_simulation_dashboard.py",
    "simulator": ROOT / "dashboard" / "live_pay_simulator.py",
    "finalizer": ROOT / "dashboard" / "live_pay_simulator_finalize.py",
}
missing_files = [str(path) for path in paths.values() if not path.exists()]
if missing_files:
    raise FileNotFoundError("AuditHero dashboard component(s) missing: " + ", ".join(missing_files))


def _load_module(name: str, path: Path):
    module_spec = importlib.util.spec_from_file_location(name, path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"AuditHero dashboard module could not be loaded: {path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


# Setup creates these immediately before this notebook. Missing simulation views are
# therefore an installation error, not a reason to silently publish the old dashboard.
required_views = [
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
missing_views = []
for view in required_views:
    full_name = f"`{catalog}`.`gold`.`{view}`"
    try:
        spark.sql(f"SELECT 1 FROM {full_name} LIMIT 1").collect()
    except Exception:
        missing_views.append(f"{catalog}.gold.{view}")
if missing_views:
    raise RuntimeError(
        "AuditHero dashboard cannot be published because Setup did not create required reporting/simulation views: "
        + ", ".join(missing_views)
    )

builder = _load_module("audithero_lakeview_builder", paths["builder"])
enhancements = _load_module("audithero_dashboard_enhancements", paths["enhancements"])
pay_review = _load_module("audithero_pay_simulation_dashboard", paths["pay_review"])
simulator = _load_module("audithero_live_pay_simulator", paths["simulator"])
finalizer = _load_module("audithero_live_pay_simulator_finalize", paths["finalizer"])

spec = json.loads(paths["spec"].read_text(encoding="utf-8"))
spec = enhancements.enhance_spec(spec)
spec = pay_review.enhance_spec(spec)
spec = simulator.enhance_spec(spec)
spec = finalizer.enhance_spec(spec)

desired_json = builder.build_dashboard(spec)
desired_text = json.dumps(desired_json, separators=(",", ":"))

if not desired_json.get("datasets") or not desired_json.get("pages"):
    raise ValueError("AuditHero dashboard definition is incomplete")
if len(desired_json["pages"]) > 15:
    raise ValueError(f"AuditHero dashboard exceeds Databricks page limit: {len(desired_json['pages'])}")

for dataset in desired_json["datasets"]:
    if not isinstance(dataset.get("queryLines"), list) or not dataset.get("queryLines"):
        raise ValueError(f"Dashboard dataset {dataset.get('name')} has no queryLines")
    for parameter in dataset.get("parameters", []) or []:
        for key in ("keyword", "displayName", "dataType", "defaultSelection"):
            if key not in parameter or parameter.get(key) in (None, ""):
                raise ValueError(f"Dashboard parameter {dataset.get('name')}.{parameter.get('keyword')} is missing {key}")

all_layout = [item for page in desired_json["pages"] for item in page.get("layout", [])]
widget_names = {item.get("widget", {}).get("name") for item in all_layout}
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
missing_widgets = sorted(required_widgets - widget_names)
if missing_widgets:
    raise RuntimeError("Generated AuditHero dashboard is missing simulator widgets: " + ", ".join(missing_widgets))

employee_page = next((p for p in desired_json["pages"] if p.get("name") == "employee_deep_dive"), None)
if employee_page is None:
    raise RuntimeError("Generated AuditHero dashboard has no Employee Deep Dive page")
employee_extent = max(
    (item.get("position", {}).get("x", 0) + item.get("position", {}).get("width", 0) for item in employee_page.get("layout", [])),
    default=0,
)
if employee_extent < 12:
    raise RuntimeError(f"Employee Deep Dive does not fill the current 12-column Databricks canvas; extent={employee_extent}")


def canonical(value):
    if isinstance(value, str):
        value = json.loads(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


w = WorkspaceClient()
api = w.api_client


def call(method: str, path: str, body=None, query=None):
    return api.do(method, path, body=body, query=query)


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


matches = [d for d in list_dashboards() if d.get("display_name") == DASHBOARD_NAME]
if not matches:
    api_parent = str(ROOT)
    if api_parent.startswith("/Workspace"):
        api_parent = api_parent[len("/Workspace"):]
    created = call(
        "POST",
        "/api/2.0/lakeview/dashboards",
        {
            "display_name": DASHBOARD_NAME,
            "warehouse_id": warehouse_id,
            "serialized_dashboard": desired_text,
            "parent_path": api_parent,
        },
        query={"dataset_catalog": catalog, "dataset_schema": "gold"},
    )
    matches = [created]
    print(f"Created AuditHero dashboard: {created['dashboard_id']}")

if len(matches) > 1:
    print(
        f"Detected {len(matches)} dashboards named '{DASHBOARD_NAME}'. "
        "AuditHero will update and publish every matching dashboard so no stale duplicate remains visible."
    )

verified_ids = []
for item in matches:
    dashboard_id = item["dashboard_id"]
    current = call("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}") or {}
    body = {
        "dashboard_id": dashboard_id,
        "display_name": DASHBOARD_NAME,
        "warehouse_id": warehouse_id,
        "serialized_dashboard": desired_text,
    }
    if current.get("etag"):
        body["etag"] = current["etag"]
    call(
        "PATCH",
        f"/api/2.0/lakeview/dashboards/{dashboard_id}",
        body,
        query={"dataset_catalog": catalog, "dataset_schema": "gold"},
    )

    stored = call("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}") or {}
    if canonical(stored.get("serialized_dashboard") or "{}") != canonical(desired_text):
        raise RuntimeError(f"Databricks did not retain enhanced dashboard definition for {dashboard_id}")

    call(
        "POST",
        f"/api/2.0/lakeview/dashboards/{dashboard_id}/published",
        {"embed_credentials": False, "warehouse_id": warehouse_id},
    )
    published = call("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}/published") or {}
    if str(published.get("warehouse_id") or "") != warehouse_id:
        raise RuntimeError(f"AuditHero dashboard {dashboard_id} was published with an unexpected SQL warehouse")

    verified_ids.append(dashboard_id)
    print(
        f"Verified enhanced dashboard {dashboard_id}; build={DASHBOARD_BUILD}; "
        f"revision={published.get('revision_create_time')}"
    )

print(f"AuditHero dashboard verification complete. Enhanced dashboard(s): {', '.join(verified_ids)}")
print("Employee Deep Dive contains Roster Pay Simulator at the top and spans the full 12-column canvas.")
print("The simulator is mandatory in this release; Setup will not silently publish the legacy/core dashboard.")
