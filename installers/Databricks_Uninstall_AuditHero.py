# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Uninstall
# MAGIC
# MAGIC Import this notebook into the Databricks workspace that contains AuditHero and
# MAGIC choose **Run all**. By default the AuditHero catalog is preserved so payroll and
# MAGIC audit evidence is not destroyed accidentally.
# MAGIC
# MAGIC To permanently remove the AuditHero catalog and all data in it, set
# MAGIC `delete_audit_data = True` and enter the exact confirmation phrase shown below.

# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20"

# COMMAND ----------
delete_audit_data = False
confirmation = ""

# Full deletion requires:
# delete_audit_data = True
# confirmation = "DELETE AUDITHERO DATA"

install_root = "/Shared/AuditHero"
default_catalog = "schads_payroll"

# COMMAND ----------
import base64
import json

from databricks.sdk import WorkspaceClient

if delete_audit_data and confirmation != "DELETE AUDITHERO DATA":
    raise ValueError("Full data deletion requires confirmation = 'DELETE AUDITHERO DATA'.")

w = WorkspaceClient()
api = w.api_client


def call(method: str, path: str, body=None, query=None):
    return api.do(method, path, body=body, query=query)


print(f"Removing AuditHero-managed resources from {w.config.host}")
print("Catalog data deletion:", "YES" if delete_audit_data else "NO — data will be preserved")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Read the installation record
# MAGIC
# MAGIC When available, the installer state identifies the jobs, dashboard and SQL
# MAGIC warehouse that AuditHero created. If the state file is unavailable, the
# MAGIC uninstaller falls back to exact AuditHero resource names.

# COMMAND ----------
state = {}
try:
    exported = call("GET", "/api/2.0/workspace/export", query={"path": f"{install_root}/install_state.json", "format": "RAW"})
    state = json.loads(base64.b64decode(exported["content"]).decode("utf-8"))
except Exception:
    print("Installation state file not found; using AuditHero resource names.")

catalog = state.get("catalog") or default_catalog

# COMMAND ----------
# MAGIC %md
# MAGIC ## Remove AuditHero jobs

# COMMAND ----------
managed_job_names = {
    "AuditHero - Setup",
    "AuditHero - Self Test",
    "AuditHero - Build Source Mapping Workbook",
    "AuditHero - Convert Source Files",
    "AuditHero - Convert Mapped Files and Run Audit",
    "AuditHero - File Readiness",
    "AuditHero - Audit Uploaded CSV Excel",
    "AuditHero - Employment Hero Connection Test (Optional API)",
    "AuditHero - API Audit Readiness (Optional API)",
    "AuditHero - Historical SCHADS Audit (Optional API)",
    "AuditHero - Monthly Payroll Audit (Optional API)",
}

job_ids = set((state.get("jobs") or {}).values())
if not job_ids:
    token = None
    while True:
        query = {"limit": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.2/jobs/list", query=query) or {}
        for job in payload.get("jobs", []) or []:
            if job.get("settings", {}).get("name") in managed_job_names:
                job_ids.add(job["job_id"])
        token = payload.get("next_page_token")
        if not token:
            break

for job_id in sorted(job_ids):
    call("POST", "/api/2.2/jobs/delete", {"job_id": job_id})
    print(f"Removed job: {job_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Unpublish and remove the AuditHero AI/BI dashboard

# COMMAND ----------
dashboard_id = state.get("dashboard_id")
if not dashboard_id:
    token = None
    while True:
        query = {"page_size": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.0/lakeview/dashboards", query=query) or {}
        dashboards = payload.get("dashboards", []) or payload.get("value", []) or []
        match = next((d for d in dashboards if d.get("display_name") == "AuditHero - SCHADS Payroll Compliance"), None)
        if match:
            dashboard_id = match["dashboard_id"]
            break
        token = payload.get("next_page_token") or payload.get("nextPageToken")
        if not token:
            break

if dashboard_id:
    try:
        call("DELETE", f"/api/2.0/lakeview/dashboards/{dashboard_id}/published")
        print(f"Unpublished AI/BI dashboard: {dashboard_id}")
    except Exception:
        # The dashboard may already be unpublished; continue with draft removal.
        pass
    call("DELETE", f"/api/2.0/lakeview/dashboards/{dashboard_id}")
    print(f"Removed AI/BI dashboard: {dashboard_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Remove SQL warehouse only when AuditHero created it

# COMMAND ----------
warehouse_id = state.get("warehouse_id")
if warehouse_id and state.get("warehouse_created_by_installer"):
    try:
        call("DELETE", f"/api/2.0/sql/warehouses/{warehouse_id}")
        print(f"Removed AuditHero-created SQL warehouse: {warehouse_id}")
    except Exception as exc:
        print(f"Warehouse could not be removed automatically: {exc}")
else:
    print("Existing/shared SQL warehouse preserved.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Remove installed AuditHero workspace code

# COMMAND ----------
try:
    call("POST", "/api/2.0/workspace/delete", {"path": install_root, "recursive": True})
    print(f"Removed workspace folder: {install_root}")
except Exception as exc:
    print(f"Workspace folder removal reported: {exc}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Optionally remove the AuditHero catalog and all data
# MAGIC
# MAGIC This is intentionally the last step. `DROP CATALOG ... CASCADE` permanently
# MAGIC removes AuditHero tables, views and the landing Volume in that catalog.

# COMMAND ----------
if delete_audit_data:
    spark.sql(f"DROP CATALOG IF EXISTS `{catalog}` CASCADE")
    print(f"Permanently removed catalog and data: {catalog}")
else:
    print(f"Preserved catalog and data: {catalog}")

print("\nAuditHero uninstall completed.")
if not delete_audit_data:
    print("Payroll/audit data remains available in the preserved catalog.")
    print("Run this notebook again with the explicit full-delete confirmation only if permanent data removal is required.")
