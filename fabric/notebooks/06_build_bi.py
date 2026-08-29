# AuditHero — Build / Refresh Power BI
#
# PURPOSE
# -------
# Create or update AuditHero's Direct Lake semantic model, business measures and
# Power BI report. Run after Setup and whenever the BI definition is upgraded.
#
# PARAMETERS
# workspace_name      — Fabric workspace containing AuditHero.
# lakehouse_name      — AuditHero Lakehouse name.
# semantic_model_name — target Direct Lake semantic model.
# report_name         — target Power BI report.
#
# IMPORTANT CONTROL
# -----------------
# Confirmed under/over-payment measures include only rows whose reconciliation
# status is UNDERPAID or OVERPAID. REQUIRES_REVIEW rows are deliberately excluded
# from headline remediation totals until their evidence is resolved.

import sempy.fabric as fabric
import Microsoft.AnalysisServices.Tabular as TOM

from sempy_labs.directlake import generate_direct_lake_semantic_model, check_fallback_reason
from sempy_labs.tom import connect_semantic_model
from sempy_labs.report import create_report_from_reportjson, update_report_from_reportjson, report_rebind
from schads_audit.fabric_powerbi import build_audithero_report_json

print("STEP 1 — Define the Lakehouse tables exposed to Power BI")
# `gold.current_*` contains the latest successful audit snapshot. Reference/run
# tables remain available so reviewers can inspect rule/readiness/run context.
TABLES = {
    "Pay Period Reconciliation": "gold.current_reconciliation",
    "Audit Detail": "gold.current_audit_detail",
    "Supplemental Entitlements": "gold.current_event_adjustments",
    "TOIL Findings": "gold.current_toil_findings",
    "Rule Coverage": "ref.rule_coverage",
    "Audit Runs": "ops.audit_runs",
    "Readiness Findings": "ops.readiness_findings",
}

print("STEP 2 — Create/refresh the Direct Lake semantic model")
generate_direct_lake_semantic_model(
    dataset=semantic_model_name,
    tables=TABLES,
    source=lakehouse_name,
    source_type="Lakehouse",
    source_workspace=workspace_name,
    use_sql_endpoint=False,
    workspace=workspace_name,
    refresh=True,
    inherit_descriptions=True,
    overwrite=True,
)

print("STEP 3 — Define payroll/audit business measures")
# Measures are kept here so the report has stable human-readable KPIs. The DAX for
# remediation amounts explicitly filters to definitive reconciliation statuses.
MEASURES = {
    "Pay Period Reconciliation": {
        "Employees Audited": ("DISTINCTCOUNT('Pay Period Reconciliation'[employee_id])", "0", "Distinct employees in the current successful audit snapshot."),
        "Pay Periods": ("COUNTROWS('Pay Period Reconciliation')", "0", "Employee pay periods audited in the current snapshot."),
        "Underpaid Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"UNDERPAID\")", "0", "Pay periods with a definite negative actual-minus-expected variance and no unresolved review condition."),
        "Overpaid Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"OVERPAID\")", "0", "Pay periods with a definite positive actual-minus-expected variance and no unresolved review condition."),
        "Requires Review Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"REQUIRES_REVIEW\")", "0", "Pay periods requiring evidence review before a definitive decision."),
        "Actual Pay Unavailable Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"ACTUAL_PAY_UNAVAILABLE\")", "0", "Expected entitlement exists but usable actual payroll earnings were not available."),
        "Compliant Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"COMPLIANT\")", "0", "Pay periods within tolerance and with no unresolved review finding."),
        "Potential Underpayment": ("SUMX(FILTER('Pay Period Reconciliation', 'Pay Period Reconciliation'[status] = \"UNDERPAID\"), -'Pay Period Reconciliation'[variance_actual_minus_expected])", "$#,##0.00;($#,##0.00)", "Definite underpayment variance only; review rows are excluded."),
        "Potential Overpayment": ("SUMX(FILTER('Pay Period Reconciliation', 'Pay Period Reconciliation'[status] = \"OVERPAID\"), 'Pay Period Reconciliation'[variance_actual_minus_expected])", "$#,##0.00;($#,##0.00)", "Definite overpayment variance only; review rows are excluded."),
        "Expected Pay": ("SUM('Pay Period Reconciliation'[expected_amount])", "$#,##0.00;($#,##0.00)", "Sum of expected auditable pay."),
        "Actual Auditable Pay": ("SUM('Pay Period Reconciliation'[actual_auditable_amount])", "$#,##0.00;($#,##0.00)", "Sum of payroll earnings mapped into actual auditable pay."),
        "Net Variance": ("SUM('Pay Period Reconciliation'[variance_actual_minus_expected])", "$#,##0.00;($#,##0.00)", "Actual auditable pay minus expected pay."),
        "Compliance Rate": ("DIVIDE([Compliant Periods], [Pay Periods] - [Requires Review Periods] - [Actual Pay Unavailable Periods])", "0.0%", "Compliance rate only among periods with a definitive decision."),
    },
    "Audit Detail": {
        "Shifts Audited": ("COUNTROWS('Audit Detail')", "0", "Shift-level audit records in the current snapshot."),
        "Review Shifts": ("CALCULATE(COUNTROWS('Audit Detail'), 'Audit Detail'[entitlement_status] = \"REQUIRES_REVIEW\")", "0", "Shift records requiring evidence/rule review."),
        "Expected Shift Entitlements": ("SUM('Audit Detail'[expected_amount])", "$#,##0.00;($#,##0.00)", "Expected shift-level Award comparator before pay-period reconciliation."),
    },
    "Supplemental Entitlements": {
        "Supplemental Expected Adjustments": ("SUM('Supplemental Entitlements'[expected_adjustment])", "$#,##0.00;($#,##0.00)", "Calculated controlled supplemental entitlements.")
    },
    "TOIL Findings": {
        "Outstanding TOIL Hours": ("SUM('TOIL Findings'[remaining_hours])", "0.00", "Remaining overtime hours in the controlled TOIL register."),
        "TOIL Payment Due": ("SUM('TOIL Findings'[expected_adjustment])", "$#,##0.00;($#,##0.00)", "Calculated payment due for TOIL items with sufficient evidence."),
    },
}

with connect_semantic_model(dataset=semantic_model_name, workspace=workspace_name, readonly=False) as tom:
    for table_name, measures in MEASURES.items():
        table = tom.model.Tables[table_name]
        existing = {measure.Name: measure for measure in table.Measures}
        for name, (expression, format_string, description) in measures.items():
            if name in existing:
                measure = existing[name]
            else:
                measure = TOM.Measure()
                measure.Name = name
                table.Measures.Add(measure)
            measure.Expression = expression
            measure.FormatString = format_string
            measure.Description = description
            measure.DisplayFolder = "AuditHero KPIs"

print("STEP 4 — Create or update the Power BI report")
report_json = build_audithero_report_json()
reports = fabric.list_reports(workspace=workspace_name)
name_column = "Name" if "Name" in reports.columns else "Report Name" if "Report Name" in reports.columns else None
exists = bool(name_column and (reports[name_column] == report_name).any())

if exists:
    update_report_from_reportjson(report=report_name, report_json=report_json, workspace=workspace_name)
else:
    create_report_from_reportjson(report=report_name, dataset=semantic_model_name, report_json=report_json, workspace=workspace_name)

# Rebind in case overwriting the semantic model created a new model ID.
report_rebind(
    report=report_name,
    dataset=semantic_model_name,
    report_workspace=workspace_name,
    dataset_workspace=workspace_name,
)

print("STEP 5 — Check Direct Lake fallback state")
fallback = check_fallback_reason(semantic_model_name, workspace=workspace_name)
display(fallback)
if "FallbackReasonID" in fallback.columns and (fallback["FallbackReasonID"] != 0).any():
    print("WARNING: one or more tables report a Direct Lake fallback reason. Review the table before production sign-off.")
else:
    print("Direct Lake model and Power BI report deployed successfully.")

notebookutils.notebook.exit("success")
