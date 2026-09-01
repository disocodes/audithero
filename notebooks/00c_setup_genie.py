# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Configure Genie
# MAGIC
# MAGIC This is a managed Setup task. It runs only after AuditHero tables/views and the
# MAGIC Unity Catalog metric views exist. Normal payroll operators do not run it directly.

# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20"

# COMMAND ----------
import json
from databricks.sdk import WorkspaceClient


dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("sql_warehouse_id", "")
dbutils.widgets.text("parent_path", "/Workspace/Shared/AuditHero")

catalog = dbutils.widgets.get("catalog").strip()
warehouse_id = dbutils.widgets.get("sql_warehouse_id").strip()
parent_path = dbutils.widgets.get("parent_path").strip() or "/Workspace/Shared/AuditHero"

if not warehouse_id:
    raise ValueError("AuditHero Genie setup requires a SQL warehouse ID.")

w = WorkspaceClient()
api = w.api_client


def call(method: str, path: str, body=None, query=None):
    return api.do(method, path, body=body, query=query)


# Ensure the workspace parent exists. Workspace APIs use /Shared/... while Genie may
# expose the same folder as /Workspace/Shared/....
workspace_parent = parent_path
if workspace_parent.startswith("/Workspace/"):
    workspace_parent = workspace_parent[len("/Workspace"):]
call("POST", "/api/2.0/workspace/mkdirs", {"path": workspace_parent})


serialized = {
    "version": 2,
    "config": {
        "sample_questions": [
            {"id": "10000000000000000000000000000001", "question": ["How much potential underpayment is in the latest successful audit?"]},
            {"id": "10000000000000000000000000000002", "question": ["Which employees have underpaid pay periods?"]},
            {"id": "10000000000000000000000000000003", "question": ["Which pay periods require human review?"]},
            {"id": "10000000000000000000000000000004", "question": ["Show expected pay and actual pay by pay period."]},
            {"id": "10000000000000000000000000000005", "question": ["Which SCHADS classifications have the most shift-level review findings?"]},
        ]
    },
    "data_sources": {
        "tables": [
            {"identifier": f"{catalog}.gold.v_audit_runs"},
            {"identifier": f"{catalog}.gold.v_readiness_findings"},
            {"identifier": f"{catalog}.gold.v_rule_coverage"},
        ],
        "metric_views": [
            {"identifier": f"{catalog}.semantic.audit_detail"},
            {"identifier": f"{catalog}.semantic.payroll_compliance"},
        ],
    },
    "instructions": {
        "example_question_sqls": [
            {
                "id": "20000000000000000000000000000001",
                "question": ["How much potential underpayment is in the latest successful audit?"],
                "sql": [f"SELECT MEASURE(potential_underpayment) AS potential_underpayment FROM {catalog}.semantic.payroll_compliance"],
            },
            {
                "id": "20000000000000000000000000000002",
                "question": ["Show underpaid pay periods by employee."],
                "sql": [f"SELECT employee_name, MEASURE(underpaid_periods) AS underpaid_periods, MEASURE(potential_underpayment) AS potential_underpayment FROM {catalog}.semantic.payroll_compliance WHERE status = 'UNDERPAID' GROUP BY employee_name ORDER BY potential_underpayment DESC"],
            },
            {
                "id": "20000000000000000000000000000003",
                "question": ["Which classifications have the most review shifts?"],
                "sql": [f"SELECT classification_code, MEASURE(review_shift_count) AS review_shift_count FROM {catalog}.semantic.audit_detail GROUP BY classification_code ORDER BY review_shift_count DESC"],
            },
        ],
        "text_instructions": [
            {
                "id": "30000000000000000000000000000001",
                "content": [
                    f"You are AuditHero Payroll Compliance, a governed analytics assistant for SCHADS payroll audit results.\nUse {catalog}.semantic.payroll_compliance first for headline payroll, variance, underpayment, overpayment and pay-period questions.\nUse {catalog}.semantic.audit_detail for shift, classification, employment type and expected-entitlement questions.\nUse {catalog}.gold.v_readiness_findings for missing-data and readiness questions.\nUse {catalog}.gold.v_rule_coverage for Award rule coverage questions.\nUse {catalog}.gold.v_audit_runs for audit execution history and run status.\nNever treat REQUIRES_REVIEW as an underpayment or include it in confirmed underpayment totals.\nPotential underpayment means only the governed potential_underpayment measure from rows classified UNDERPAID.\nWhen explaining a finding, state the audit status and distinguish calculated expected entitlement from actual payroll.\nDo not invent SCHADS clauses or legal conclusions that are not present in the governed AuditHero data.\nPrefer metric-view measures through MEASURE() instead of recalculating business KPIs from raw tables.\nDo not query Bronze or Silver assets for business answers."
                ],
            }
        ],
    },
}
serialized_space = json.dumps(serialized, separators=(",", ":"))


def list_spaces():
    spaces = []
    token = None
    while True:
        query = {"page_size": 100}
        if token:
            query["page_token"] = token
        payload = call("GET", "/api/2.0/genie/spaces", query=query) or {}
        spaces.extend(payload.get("spaces", []) or payload.get("value", []) or [])
        token = payload.get("next_page_token") or payload.get("nextPageToken")
        if not token:
            return spaces


title = "AuditHero - Payroll Compliance"
description = "Ask governed natural-language questions about AuditHero SCHADS payroll audit results, readiness, rule coverage and audit history."
existing = next((s for s in list_spaces() if s.get("title") == title), None)
body = {
    "warehouse_id": warehouse_id,
    "title": title,
    "description": description,
    "parent_path": parent_path,
    "serialized_space": serialized_space,
}

if existing:
    space_id = existing.get("space_id") or existing.get("id")
    result = call("PATCH", f"/api/2.0/genie/spaces/{space_id}", body)
    print(f"Updated Genie Agent: {title} ({space_id})")
else:
    result = call("POST", "/api/2.0/genie/spaces", body)
    space_id = result.get("space_id") or result.get("id")
    print(f"Created Genie Agent: {title} ({space_id})")

print(f"Trusted semantic assets: {catalog}.semantic.payroll_compliance, {catalog}.semantic.audit_detail")
dbutils.notebook.exit(str(space_id or ""))
