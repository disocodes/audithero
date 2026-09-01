# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Verify AI/BI Dashboard
# MAGIC
# MAGIC **Purpose:** ensure the managed AuditHero AI/BI dashboard stored in Databricks matches the dashboard definition installed with the current AuditHero release.
# MAGIC
# MAGIC This notebook is run by **AuditHero - Setup**. It updates and republishes the managed dashboard when the stored draft differs from the installed definition, then verifies the stored draft after the update.
# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20"
# COMMAND ----------
from pathlib import Path
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
DASHBOARD_FILE = ROOT / "dashboard" / "payroll_compliance.lvdash.json"
if not DASHBOARD_FILE.exists():
    raise FileNotFoundError(f"AuditHero dashboard definition not found: {DASHBOARD_FILE}")

desired_text = DASHBOARD_FILE.read_text(encoding="utf-8")
desired_json = json.loads(desired_text)

# Validate the portable dashboard structure before calling the Lakeview API.
if not desired_json.get("datasets"):
    raise ValueError("AuditHero dashboard definition contains no datasets")
if not desired_json.get("pages"):
    raise ValueError("AuditHero dashboard definition contains no pages")
if not all(isinstance(ds.get("queryLines"), list) and ds.get("queryLines") for ds in desired_json["datasets"]):
    raise ValueError("AuditHero dashboard datasets must use non-empty queryLines arrays")
if not any(
    item.get("widget", {}).get("queries")
    for page in desired_json["pages"]
    for item in page.get("layout", [])
):
    raise ValueError("AuditHero dashboard definition contains no data-backed widgets")


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
        call(
            "PATCH",
            f"/api/2.0/lakeview/dashboards/{dashboard_id}",
            {
                "dashboard_id": dashboard_id,
                "display_name": DASHBOARD_NAME,
                "warehouse_id": warehouse_id,
                "serialized_dashboard": desired_text,
                "etag": current.get("etag"),
            },
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
