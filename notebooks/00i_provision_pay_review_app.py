# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Provision Pay Review App
# MAGIC
# MAGIC Creates or updates the Databricks App used for live roster-pay simulation and rate-confirmation write-back.
# MAGIC The app uses its own service principal and an existing SQL warehouse resource with `CAN_USE` only.
# MAGIC Failure to provision Databricks Apps is reported without disabling the core AuditHero calculation/dashboard workflow.
# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.60"
# COMMAND ----------
import re
import time

from databricks.sdk import WorkspaceClient

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("sql_warehouse_id", "")
dbutils.widgets.text("git_ref", "main")

catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"
warehouse_id = dbutils.widgets.get("sql_warehouse_id").strip()
git_ref = dbutils.widgets.get("git_ref").strip() or "main"

if not warehouse_id:
    raise ValueError("sql_warehouse_id is required to provision the AuditHero Pay Review app")

APP_NAME = "audithero-pay-review"
APP_DESCRIPTION = "AuditHero roster pay simulator, manual rate confirmation and employee master review"
REPOSITORY_URL = "https://github.com/disocodes/audithero.git"
APP_SOURCE_PATH = "apps/pay_review"

w = WorkspaceClient()
api = w.api_client


def call(method: str, path: str, body=None, query=None):
    return api.do(method, path, body=body, query=query)


def list_apps():
    rows = []
    token = None
    while True:
        query = {"page_size": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.0/apps", query=query) or {}
        rows.extend(payload.get("apps", []) or [])
        token = payload.get("next_page_token")
        if not token:
            return rows


def wait_for_update(timeout_seconds=300):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = call("GET", f"/api/2.0/apps/{APP_NAME}/update") or {}
        state = str((payload.get("status") or {}).get("state") or "")
        message = str((payload.get("status") or {}).get("message") or "")
        if state == "SUCCEEDED":
            return
        if state == "FAILED":
            raise RuntimeError(f"Databricks App update failed: {message}")
        time.sleep(3)
    raise TimeoutError("Timed out waiting for AuditHero Pay Review app configuration update")


def wait_for_deployment(deployment_id: str, timeout_seconds=600):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = call("GET", f"/api/2.0/apps/{APP_NAME}/deployments/{deployment_id}") or {}
        status = payload.get("status") or {}
        state = str(status.get("state") or "")
        message = str(status.get("message") or "")
        if state == "SUCCEEDED":
            return payload
        if state in {"FAILED", "CANCELLED"}:
            raise RuntimeError(f"AuditHero Pay Review app deployment failed: {message}")
        time.sleep(4)
    raise TimeoutError("Timed out waiting for AuditHero Pay Review app deployment")


app_body = {
    "name": APP_NAME,
    "description": APP_DESCRIPTION,
    "compute_size": "MEDIUM",
    "resources": [
        {
            "name": "sql-warehouse",
            "description": "AuditHero SQL warehouse",
            "sql_warehouse": {"id": warehouse_id, "permission": "CAN_USE"},
        }
    ],
    "git_repository": {
        "url": REPOSITORY_URL,
        "provider": "gitHub",
        "auto_deploy": False,
    },
}

try:
    existing = next((app for app in list_apps() if app.get("name") == APP_NAME), None)
    if existing is None:
        call("POST", "/api/2.0/apps", app_body, query={"no_compute": "true"})
        print(f"Created Databricks App: {APP_NAME}")
    else:
        call("POST", f"/api/2.0/apps/{APP_NAME}/update", {"app": app_body})
        wait_for_update()
        print(f"Updated Databricks App configuration: {APP_NAME}")

    app = call("GET", f"/api/2.0/apps/{APP_NAME}") or {}
    service_principal_client_id = str(app.get("service_principal_client_id") or "").strip()
    if not service_principal_client_id:
        raise RuntimeError("Databricks did not return the Pay Review app service principal client ID")

    git_source = {"source_code_path": APP_SOURCE_PATH}
    if re.fullmatch(r"[0-9a-fA-F]{40}", git_ref):
        git_source["commit"] = git_ref
    elif git_ref.startswith("refs/tags/"):
        git_source["tag"] = git_ref.removeprefix("refs/tags/")
    else:
        git_source["branch"] = git_ref.removeprefix("refs/heads/")

    deployment = call(
        "POST",
        f"/api/2.0/apps/{APP_NAME}/deployments",
        {
            "git_source": git_source,
            "mode": "SNAPSHOT",
            "env_vars": [
                {"name": "WAREHOUSE_ID", "value_from": "sql-warehouse"},
                {"name": "AUDITHERO_CATALOG", "value": catalog},
            ],
        },
    ) or {}
    deployment_id = str(deployment.get("deployment_id") or "").strip()
    if not deployment_id:
        raise RuntimeError("Databricks did not return a Pay Review app deployment ID")
    wait_for_deployment(deployment_id)
    call("POST", f"/api/2.0/apps/{APP_NAME}/start", {})

    app = call("GET", f"/api/2.0/apps/{APP_NAME}") or {}
    print(f"AuditHero Pay Review app deployed: {app.get('url') or APP_NAME}")
    print(f"App service principal client ID: {service_principal_client_id}")
    dbutils.notebook.exit(service_principal_client_id)
except Exception as exc:
    print(
        "WARNING: AuditHero could not provision the Databricks Pay Review app. "
        "Roster simulation views can still be created and the core audit remains available."
    )
    print(f"App provisioning detail: {type(exc).__name__}: {exc}")
    dbutils.notebook.exit("")
