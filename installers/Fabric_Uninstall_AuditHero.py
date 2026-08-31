# Fabric notebook source
# METADATA ********************
# META {
# META   "kernel_info": {"name": "synapse_pyspark"},
# META   "language_info": {"name": "python"}
# META }

# CELL ********************

# AuditHero — Uninstall
#
# Run this notebook from the installed AuditHero administration notebooks. By
# default the Lakehouse is preserved so payroll/audit evidence is not destroyed
# accidentally. Set delete_audit_data=True and enter the exact confirmation phrase
# to remove the AuditHero Lakehouse and its data as well.

# CELL ********************

delete_audit_data = False
confirmation = ""
lakehouse_name = "AuditHero_Lakehouse"
environment_name = "AuditHero_Environment"
semantic_model_name = "AuditHero - SCHADS Payroll Compliance"
report_name = "AuditHero - SCHADS Payroll Compliance"

# To permanently remove the AuditHero Lakehouse and its data, use:
# delete_audit_data = True
# confirmation = "DELETE AUDITHERO DATA"

# CELL ********************

import time
import requests


def _context_value(name: str):
    ctx = notebookutils.runtime.context
    if isinstance(ctx, dict):
        return ctx.get(name)
    return getattr(ctx, name, None)


workspace_id = _context_value("currentWorkspaceId")
workspace_name = _context_value("currentWorkspaceName")
current_notebook_id = _context_value("currentNotebookId")
if not workspace_id:
    raise RuntimeError("Fabric workspace ID could not be detected from this notebook session.")
if delete_audit_data and confirmation != "DELETE AUDITHERO DATA":
    raise ValueError("Full data deletion requires confirmation = 'DELETE AUDITHERO DATA'.")

print(f"Removing AuditHero-managed items from: {workspace_name} ({workspace_id})")
print("Lakehouse data deletion:", "YES" if delete_audit_data else "NO — data will be preserved")

# CELL ********************

API = "https://api.fabric.microsoft.com/v1"
token = notebookutils.credentials.getToken("pbi")
session = requests.Session()
session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})


def get_items():
    items = []
    url = f"{API}/workspaces/{workspace_id}/items"
    while url:
        r = session.get(url, timeout=120)
        r.raise_for_status()
        payload = r.json()
        items.extend(payload.get("value", []))
        token_value = payload.get("continuationToken")
        url = f"{API}/workspaces/{workspace_id}/items?continuationToken={token_value}" if token_value else None
    return items


def wait_until_absent(item_id: str, timeout_seconds: int = 300):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not any(i.get("id") == item_id for i in get_items()):
            return
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for Fabric item deletion: {item_id}")


def delete_item(item):
    r = session.delete(f"{API}/workspaces/{workspace_id}/items/{item['id']}", timeout=120)
    if r.status_code not in (200, 202, 204, 404):
        raise RuntimeError(f"Could not delete {item.get('displayName')}: {r.status_code} {r.text}")
    if r.status_code != 404:
        wait_until_absent(item["id"])
    print(f"Removed: {item.get('type')} — {item.get('displayName')}")


managed_names = {
    "AuditHero - Install or Upgrade",
    "AuditHero - Uninstall",
    "AuditHero - Setup",
    "AuditHero - Self Test",
    "AuditHero - Employment Hero Connection",
    "AuditHero - Readiness",
    "AuditHero - Historical Audit",
    "AuditHero - Monthly Audit",
    "AuditHero - Build BI",
    "AuditHero - File Readiness",
    "AuditHero - Audit Uploaded CSV Excel",
    "AuditHero - Build Source Mapping Workbook",
    "AuditHero - Convert Source Files",
    "AuditHero - Convert Mapped Files and Run Audit",
    "AuditHero - Historical Audit Pipeline",
    "AuditHero - Monthly Payroll Pipeline",
    "AuditHero - Uploaded Files Audit Pipeline",
    semantic_model_name,
    report_name,
    environment_name,
}

items = get_items()

# Delete dependent items first. The currently running uninstaller is deferred to
# the final operation so its own session can finish the rest of the cleanup.
priority = {
    "DataPipeline": 10,
    "Report": 20,
    "SemanticModel": 30,
    "Notebook": 40,
    "Environment": 50,
    "Lakehouse": 90,
}

targets = [
    i for i in items
    if i.get("displayName") in managed_names
    and i.get("type") != "Lakehouse"
    and i.get("id") != current_notebook_id
]
targets.sort(key=lambda i: priority.get(i.get("type"), 60))

for item in targets:
    delete_item(item)

# CELL ********************

# The Lakehouse is intentionally separate from normal uninstall because deleting
# it permanently removes payroll source files, audit evidence and Delta tables.
if delete_audit_data:
    items = get_items()
    lakehouse = next((i for i in items if i.get("type") == "Lakehouse" and i.get("displayName") == lakehouse_name), None)
    if lakehouse:
        delete_item(lakehouse)
    else:
        print(f"{lakehouse_name} was not found.")
else:
    print(f"Preserved: Lakehouse — {lakehouse_name}")

print("\nAuditHero uninstall completed.")
if not delete_audit_data:
    print("The AuditHero Lakehouse and its payroll/audit data remain in the workspace.")
    print("Run the installer again later if AuditHero needs to be reinstalled against the preserved data.")

# Delete the running uninstaller last. Do not poll after this request because its
# workspace item is the notebook executing the current session.
if current_notebook_id:
    cleanup = session.delete(f"{API}/workspaces/{workspace_id}/items/{current_notebook_id}", timeout=120)
    if cleanup.status_code not in (200, 202, 204, 404):
        print(f"The running uninstaller notebook could not remove itself automatically: {cleanup.status_code}")
