# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Configure Genie
# MAGIC
# MAGIC **Purpose:** create or update the **AuditHero - Payroll Compliance** Genie space after the governed Gold views and Unity Catalog metric views have been created.
# MAGIC
# MAGIC This notebook is invoked by **AuditHero - Setup**.

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
            {"id": "10000000000000000000000000000003", "question": ["What should this employee have been paid as a SCHADS Level 3 employee?"]},
            {"id": "10000000000000000000000000000004", "question": ["Compare the employee's supplied hourly rate with the SCHADS minimum over time."]},
            {"id": "10000000000000000000000000000005", "question": ["Show the overtime components calculated for this employee under the selected SCHADS level."]},
            {"id": "10000000000000000000000000000006", "question": ["Which employees did not receive the required rest between work periods?"]},
            {"id": "10000000000000000000000000000007", "question": ["Show rest-after-overtime cases and any calculated double-time top-up."]},
            {"id": "10000000000000000000000000000008", "question": ["Which Award criteria still require evidence before the result is definitive?"]},
        ]
    },
    "data_sources": {
        "tables": [
            {"identifier": f"{catalog}.gold.v_audit_runs"},
            {"identifier": f"{catalog}.gold.v_readiness_findings"},
            {"identifier": f"{catalog}.gold.v_rule_coverage"},
            {"identifier": f"{catalog}.gold.v_rest_break_findings_latest"},
            {"identifier": f"{catalog}.gold.v_award_scenario_detail_latest"},
            {"identifier": f"{catalog}.gold.v_award_criteria_detail_latest"},
            {"identifier": f"{catalog}.gold.v_award_scenario_rest_findings_latest"},
        ],
        "metric_views": [
            {"identifier": f"{catalog}.semantic.audit_detail"},
            {"identifier": f"{catalog}.semantic.payroll_compliance"},
            {"identifier": f"{catalog}.semantic.rest_break_compliance"},
            {"identifier": f"{catalog}.semantic.award_scenarios"},
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
                "question": ["Show expected pay for Level 3 scenarios by employment type."],
                "sql": [f"SELECT employment_type, MEASURE(expected_pay) AS expected_pay FROM {catalog}.semantic.award_scenarios WHERE classification_level = 3 GROUP BY employment_type ORDER BY employment_type"],
            },
            {
                "id": "20000000000000000000000000000003",
                "question": ["Compare supplied base rate with the SCHADS Level 3 minimum over time."],
                "sql": [f"SELECT employee_name, shift_start, source_rate_effective_from, supplied_base_hourly_rate, base_hourly_rate AS award_minimum_base_rate, base_rate_variance, base_rate_status, scenario_classification_code, scenario_employment_type FROM {catalog}.gold.v_award_scenario_detail_latest WHERE scenario_level = 3 ORDER BY employee_name, shift_start"],
            },
            {
                "id": "20000000000000000000000000000004",
                "question": ["Show overtime calculation components for Level 3 scenarios."],
                "sql": [f"SELECT employee_name, shift_start, scenario_classification_code, scenario_employment_type, criterion, hours, multiplier, effective_hourly_rate, criterion_amount, clause, detail FROM {catalog}.gold.v_award_criteria_detail_latest WHERE scenario_level = 3 AND criterion_group = 'OVERTIME' ORDER BY employee_name, shift_start"],
            },
            {
                "id": "20000000000000000000000000000005",
                "question": ["Which employees had a short rest between work periods?"],
                "sql": [f"SELECT employee_name, previous_shift_end, next_shift_start, required_rest_hours, actual_rest_hours, rest_shortfall_hours, status, payment_status FROM {catalog}.gold.v_rest_break_findings_latest WHERE rest_shortfall_hours > 0 ORDER BY next_shift_start"],
            },
            {
                "id": "20000000000000000000000000000006",
                "question": ["How much double-time top-up was calculated for rest-after-overtime cases?"],
                "sql": [f"SELECT MEASURE(double_time_topup) AS double_time_topup, MEASURE(overtime_rest_cases) AS overtime_rest_cases FROM {catalog}.semantic.rest_break_compliance"],
            },
            {
                "id": "20000000000000000000000000000007",
                "question": ["Show Award scenario findings that still require evidence."],
                "sql": [f"SELECT employee_name, shift_start, scenario_classification_code, scenario_employment_type, criterion_group, detail FROM {catalog}.gold.v_award_criteria_detail_latest WHERE criterion = 'EVIDENCE_OR_RULE_REVIEW' ORDER BY employee_name, shift_start"],
            },
        ],
        "text_instructions": [
            {
                "id": "30000000000000000000000000000001",
                "content": [
                    f"You are AuditHero Payroll Compliance, a governed analytics assistant for SCHADS payroll audit results and Award scenario analysis.\nUse {catalog}.semantic.payroll_compliance first for definitive actual-versus-expected payroll, variance, underpayment, overpayment and pay-period questions.\nUse {catalog}.semantic.audit_detail for the definitive shift calculation where the employee's classification and employment facts are known.\nUse {catalog}.semantic.award_scenarios and {catalog}.gold.v_award_scenario_detail_latest when the user asks what SCHADS would require under a selected stream, level, pay point or employment type, or when comparing classifications.\nAward scenarios are analytical calculations. Do not describe a scenario as the employee's legally established classification unless the governed source facts establish that classification.\nUse {catalog}.gold.v_award_criteria_detail_latest for penalties, shiftwork, public holiday, minimum engagement, overtime, meal-break, sleepover, broken-shift, allowance and evidence-required component questions.\nUse supplied_base_hourly_rate, source_rate_effective_from, base_hourly_rate, base_rate_variance and base_rate_status from the Award scenario detail when answering historical base-rate questions. A supplied base hourly rate is evidence about the nominal base rate and is not the same as complete actual shift pay.\nOnly describe a scenario as UNDERPAID or OVERPAID when scenario_status is governed as such from an explicit actual shift amount. Otherwise report the calculated expected amount and base-rate comparison without inventing actual pay.\nUse {catalog}.semantic.rest_break_compliance and {catalog}.gold.v_rest_break_findings_latest for definitive rest-between-work findings. Use {catalog}.gold.v_award_scenario_rest_findings_latest when the question explicitly concerns rest consequences under a selected Award scenario.\nFor rest questions, report the applicable required_rest_hours, actual_rest_hours, rest_shortfall_hours, status and payment_status. A general short-rest finding is not automatically a monetary underpayment. Only report double_time_topup when AuditHero calculated it from supported evidence.\nIf a governed status or payment_status is REQUIRES_REVIEW, explain the available review reason and do not invent employer instruction, agreement, release time or a dollar entitlement.\nUse {catalog}.gold.v_readiness_findings for missing-source questions, {catalog}.gold.v_rule_coverage for Award rule coverage and {catalog}.gold.v_audit_runs for audit execution history.\nNever treat REQUIRES_REVIEW as confirmed underpayment. Potential underpayment means only the governed potential_underpayment measure from rows classified UNDERPAID.\nDo not invent SCHADS clauses or legal conclusions that are not present in the governed AuditHero results. Prefer metric-view measures through MEASURE() for governed KPIs. Do not query Bronze or Silver assets for business answers."
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
description = "Ask governed natural-language questions about SCHADS payroll outcomes, Award scenarios, historical rates, entitlement criteria, evidence requirements and audit history."
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
    call("PATCH", f"/api/2.0/genie/spaces/{space_id}", body)
    print(f"Updated Genie space: {title} ({space_id})")
else:
    result = call("POST", "/api/2.0/genie/spaces", body)
    space_id = result.get("space_id") or result.get("id")
    print(f"Created Genie space: {title} ({space_id})")

print(
    "Semantic sources: "
    f"{catalog}.semantic.payroll_compliance, "
    f"{catalog}.semantic.audit_detail, "
    f"{catalog}.semantic.rest_break_compliance, "
    f"{catalog}.semantic.award_scenarios"
)
dbutils.notebook.exit(str(space_id or ""))
