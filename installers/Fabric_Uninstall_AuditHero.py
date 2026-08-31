# Fabric notebook source
# METADATA ********************
# META {
# META   "kernel_info": {"name": "synapse_pyspark"},
# META   "language_info": {"name": "python"}
# META }

# CELL ********************

# AuditHero — Uninstall
#
# Import this notebook into the Fabric workspace that contains AuditHero and run
# all cells. By default the Lakehouse is preserved so payroll/audit evidence is
# not destroyed accidentally. Set delete_audit_data=True and enter the exact
# confirmation phrase to remove the AuditHero Lakehouse and its data as well.

# CELL ********************

delete_audit_data = False
confirmation = ""

# To permanently remove the AuditHero Lakehouse and its data, use:
# delete_audit_data = True
# confirmation = "DELETE AUDITHERO DATA"

# CELL ********************

import requests


def _context_value(name: str):
    ctx = notebookutils.runtime.context
    if isinstance(ctx, dict):
        return ctx.get(name)
    return getattr(ctx, name, None)


workspace_id = _context_value("currentWorkspaceId")
workspace_name = _context_value("currentWorkspaceName")
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


def delete_item(item):
    r = session.delete(f"{API}/workspaces/{workspace_id}/items/{item['id']}", timeout=120)
    if r.status_code not in (200, 202, 204, 404):
        raise RuntimeError(f"Could not delete {item.get('displayName')}: {r.status_code} {r.text}")
    print(f"Removed: {item.get('type')} — {item.get('displayName')}")


managed_names = {
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
    "AuditHero - SCHADS Payroll Compliance",
    "AuditHero_Environment",
}

items = get_items()

# Delete dependent items first: pipelines/reports/models, then notebooks/environment.
priority = {
    "DataPipeline": 10,
    "Report": 20,
    "SemanticModel": 30,
    "Notebook": 40,
    "Environment": 50,
    "Lakehouse": 90,
}

targets = [i for i in items if i.get("displayName") in managed_names]
targets.sort(key=lambda i: priority.get(i.get("type"), 60))

for item in targets:
    delete_item(item)

# CELL ********************

# The Lakehouse is intentionally separate from normal uninstall because deleting
# it permanently removes payroll source files, audit evidence and Delta tables.
if delete_audit_data:
    items = get_items()
    lakehouse = next((i for i in items if i.get("type") == "Lakehouse" and i.get("displayName") == "AuditHero_Lakehouse"), None)
    if lakehouse:
        delete_item(lakehouse)
    else:
        print("AuditHero_Lakehouse was not found.")
else:
    print("Preserved: Lakehouse — AuditHero_Lakehouse")

print("\nAuditHero uninstall completed.")
if not delete_audit_data:
    print("The AuditHero Lakehouse and its payroll/audit data remain in the workspace.")
    print("Run this notebook again with the explicit full-delete confirmation if permanent data removal is required.")
