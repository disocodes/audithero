# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Verify AI/BI Dashboard
# MAGIC
# MAGIC **Purpose:** build the managed AuditHero AI/BI dashboard from its version-controlled specification, then ensure the stored and published Databricks dashboard matches that definition.
# MAGIC
# MAGIC This notebook is run by **AuditHero - Setup** after the interactive investigation view has been created.
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
SPEC_FILE = ROOT / "dashboard" / "payroll_compliance.spec.json"
BUILDER_FILE = ROOT / "dashboard" / "lakeview_builder.py"
if not SPEC_FILE.exists():
    raise FileNotFoundError(f"AuditHero dashboard specification not found: {SPEC_FILE}")
if not BUILDER_FILE.exists():
    raise FileNotFoundError(f"AuditHero dashboard builder not found: {BUILDER_FILE}")

module_spec = importlib.util.spec_from_file_location("audithero_lakeview_builder", BUILDER_FILE)
if module_spec is None or module_spec.loader is None:
    raise RuntimeError("AuditHero dashboard builder could not be loaded")
builder = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(builder)

dashboard_spec = json.loads(SPEC_FILE.read_text(encoding="utf-8"))
desired_json = builder.build_dashboard(dashboard_spec)
desired_text = json.dumps(desired_json, separators=(",", ":"))

# Validate the generated dashboard before calling the Lakeview API.
if not desired_json.get("datasets"):
    raise ValueError("AuditHero dashboard definition contains no datasets")
if not desired_json.get("pages"):
    raise ValueError("AuditHero dashboard definition contains no pages")
if not all(isinstance(ds.get("queryLines"), list) and ds.get("queryLines") for ds in desired_json["datasets"]):
    raise ValueError("AuditHero dashboard datasets must use non-empty queryLines arrays")

widgets = [
    item.get("widget", {})
    for page in desired_json["pages"]
    for item in page.get("layout", [])
]
if not any(widget.get("queries") for widget in widgets):
    raise ValueError("AuditHero dashboard definition contains no data-backed widgets")
filter_widgets = [
    widget for widget in widgets
    if str(widget.get("spec", {}).get("widgetType", "")).startswith("filter-")
]
if not filter_widgets:
    raise ValueError("AuditHero dashboard definition contains no interactive filters")
for widget in filter_widgets:
    if widget.get("spec", {}).get("version") != 2:
        raise ValueError("AuditHero dashboard filters must use Lakeview filter specification version 2")
    for query in widget.get("queries", []):
        fields = query.get("query", {}).get("fields", [])
        if len(fields) != 1 or not fields[0].get("expression"):
            raise ValueError("AuditHero dashboard field filters must bind directly to one dataset field")
        if "associative_filter_predicate_group" in json.dumps(query):
            raise ValueError("AuditHero dashboard contains an obsolete filter associativity expression")

# The investigation dataset must exist before the dashboard is published.
spark.sql(f"SELECT 1 FROM `{catalog}`.`gold`.`v_audit_investigation_latest` LIMIT 1")


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

verified_ids = []
for item in matches:
    dashboard_id = item["dashboard_id"]
    current = call("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}") or {}
    current_text = current.get("serialized_dashboard") or "{}"

    if canonical(current_text) != canonical(desired_text) or current.get("warehouse_id") != warehouse_id:
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
        print(f"Updated AuditHero dashboard draft: {dashboard_id}")
    else:
        print(f"AuditHero dashboard draft already current: {dashboard_id}")

    stored = call("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}") or {}
    if canonical(stored.get("serialized_dashboard") or "{}") != canonical(desired_text):
        raise RuntimeError(
            f"Databricks did not retain the AuditHero dashboard definition for dashboard {dashboard_id}."
        )

    call(
        "POST",
        f"/api/2.0/lakeview/dashboards/{dashboard_id}/published",
        {"embed_credentials": False, "warehouse_id": warehouse_id},
    )
    published = call("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}/published") or {}
    if str(published.get("warehouse_id") or "") != warehouse_id:
        raise RuntimeError(f"AuditHero dashboard {dashboard_id} was published with an unexpected SQL warehouse")

    verified_ids.append(dashboard_id)
    print(f"Verified and published dashboard {dashboard_id}; revision={published.get('revision_create_time')}")

print(f"AuditHero dashboard verification complete. Managed dashboard(s): {', '.join(verified_ids)}")
print("Interactive investigation filters are active for status, employee, employment type, classification, work group, state and employee-pay-period.")
