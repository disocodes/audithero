# Parameters: workspace_name, lakehouse_name, semantic_model_name, report_name
import sempy.fabric as fabric
import Microsoft.AnalysisServices.Tabular as TOM

from sempy_labs.directlake import generate_direct_lake_semantic_model, check_fallback_reason
from sempy_labs.tom import connect_semantic_model
from sempy_labs.report import (
    create_report_from_reportjson,
    update_report_from_reportjson,
    report_rebind,
)
from schads_audit.fabric_powerbi import build_audithero_report_json

TABLES = {
    "Pay Period Reconciliation": "gold.current_reconciliation",
    "Audit Detail": "gold.current_audit_detail",
    "Supplemental Entitlements": "gold.current_event_adjustments",
    "TOIL Findings": "gold.current_toil_findings",
    "Rule Coverage": "ref.rule_coverage",
    "Audit Runs": "ops.audit_runs",
    "Readiness Findings": "ops.readiness_findings",
}

print("Creating/updating Direct Lake semantic model...")
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

MEASURES = {
    "Pay Period Reconciliation": {
        "Employees Audited": (
            "DISTINCTCOUNT('Pay Period Reconciliation'[employee_id])",
            "0",
            "Distinct employees in the current successful audit snapshot.",
        ),
        "Pay Periods": (
            "COUNTROWS('Pay Period Reconciliation')",
            "0",
            "Employee pay periods audited in the current snapshot.",
        ),
        "Underpaid Periods": (
            "CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"UNDERPAID\")",
            "0",
            "Pay periods with a definite negative actual-minus-expected variance and no unresolved review condition.",
        ),
        "Overpaid Periods": (
            "CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"OVERPAID\")",
            "0",
            "Pay periods with a definite positive actual-minus-expected variance and no unresolved review condition.",
        ),
        "Requires Review Periods": (
            "CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"REQUIRES_REVIEW\")",
            "0",
            "Pay periods that must not be treated as compliant or remediated until evidence is resolved.",
        ),
        "Actual Pay Unavailable Periods": (
            "CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"ACTUAL_PAY_UNAVAILABLE\")",
            "0",
            "Entitlement calculations for which actual payroll earnings were not available.",
        ),
        "Compliant Periods": (
            "CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"COMPLIANT\")",
            "0",
            "Pay periods within the configured variance tolerance and with no unresolved review finding.",
        ),
        "Potential Underpayment": (
            "SUMX(FILTER('Pay Period Reconciliation', 'Pay Period Reconciliation'[status] = \"UNDERPAID\"), -'Pay Period Reconciliation'[variance_actual_minus_expected])",
            "$#,##0.00;($#,##0.00)",
            "Definite underpayment variance only. REQUIRES_REVIEW rows are deliberately excluded.",
        ),
        "Potential Overpayment": (
            "SUMX(FILTER('Pay Period Reconciliation', 'Pay Period Reconciliation'[status] = \"OVERPAID\"), 'Pay Period Reconciliation'[variance_actual_minus_expected])",
            "$#,##0.00;($#,##0.00)",
            "Definite overpayment variance only. REQUIRES_REVIEW rows are deliberately excluded.",
        ),
        "Expected Pay": (
            "SUM('Pay Period Reconciliation'[expected_amount])",
            "$#,##0.00;($#,##0.00)",
            "Sum of expected auditable pay for the selected context.",
        ),
        "Actual Auditable Pay": (
            "SUM('Pay Period Reconciliation'[actual_auditable_amount])",
            "$#,##0.00;($#,##0.00)",
            "Sum of Employment Hero earnings categories explicitly mapped as auditable work or allowance.",
        ),
        "Net Variance": (
            "SUM('Pay Period Reconciliation'[variance_actual_minus_expected])",
            "$#,##0.00;($#,##0.00)",
            "Actual auditable pay minus expected pay.",
        ),
        "Compliance Rate": (
            "DIVIDE([Compliant Periods], [Pay Periods] - [Requires Review Periods] - [Actual Pay Unavailable Periods])",
            "0.0%",
            "Compliance rate among periods for which a definitive compliance decision is available.",
        ),
    },
    "Audit Detail": {
        "Shifts Audited": ("COUNTROWS('Audit Detail')", "0", "Shift-level audit records in the current snapshot."),
        "Review Shifts": (
            "CALCULATE(COUNTROWS('Audit Detail'), 'Audit Detail'[entitlement_status] = \"REQUIRES_REVIEW\")",
            "0",
            "Shift records requiring evidence or rule review.",
        ),
        "Expected Shift Entitlements": (
            "SUM('Audit Detail'[expected_amount])",
            "$#,##0.00;($#,##0.00)",
            "Expected shift-level Award comparator before pay-period reconciliation.",
        ),
    },
    "Supplemental Entitlements": {
        "Supplemental Expected Adjustments": (
            "SUM('Supplemental Entitlements'[expected_adjustment])",
            "$#,##0.00;($#,##0.00)",
            "Calculated on-call, recall, remote work, higher duties and other controlled supplemental entitlements.",
        )
    },
    "TOIL Findings": {
        "Outstanding TOIL Hours": (
            "SUM('TOIL Findings'[remaining_hours])",
            "0.00",
            "Remaining overtime hours in the controlled TOIL register.",
        ),
        "TOIL Payment Due": (
            "SUM('TOIL Findings'[expected_adjustment])",
            "$#,##0.00;($#,##0.00)",
            "Calculated overtime payment due for TOIL items with sufficient controlled evidence.",
        ),
    },
}

print("Adding/updating business measures...")
with connect_semantic_model(
    dataset=semantic_model_name,
    workspace=workspace_name,
    readonly=False,
) as tom:
    for table_name, measures in MEASURES.items():
        table = tom.model.Tables[table_name]
        existing = {m.Name: m for m in table.Measures}
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

report_json = build_audithero_report_json()
reports = fabric.list_reports(workspace=workspace_name)
name_column = "Name" if "Name" in reports.columns else "Report Name" if "Report Name" in reports.columns else None
exists = bool(name_column and (reports[name_column] == report_name).any())

if exists:
    print("Updating Power BI report definition...")
    update_report_from_reportjson(
        report=report_name,
        report_json=report_json,
        workspace=workspace_name,
    )
else:
    print("Creating Power BI report...")
    create_report_from_reportjson(
        report=report_name,
        dataset=semantic_model_name,
        report_json=report_json,
        workspace=workspace_name,
    )

# Rebind after every deployment in case overwrite created a new semantic-model ID.
report_rebind(
    report=report_name,
    dataset=semantic_model_name,
    report_workspace=workspace_name,
    dataset_workspace=workspace_name,
)

print("Checking Direct Lake fallback state...")
fallback = check_fallback_reason(semantic_model_name, workspace=workspace_name)
display(fallback)
if "FallbackReasonID" in fallback.columns and (fallback["FallbackReasonID"] != 0).any():
    print("WARNING: one or more tables report a Direct Lake fallback reason. Review the table above before production sign-off.")
else:
    print("Direct Lake model and Power BI report deployed successfully.")

notebookutils.notebook.exit("success")
