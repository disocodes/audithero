# AuditHero — Build / Refresh Power BI
#
# PURPOSE
# -------
# Create or update AuditHero's Direct Lake semantic model, business measures and
# Power BI report. Run after Setup and when the AuditHero BI definition is upgraded.
#
# PARAMETERS
# workspace_name      — Fabric workspace containing AuditHero.
# lakehouse_name      — AuditHero Lakehouse name.
# semantic_model_name — target Direct Lake semantic model.
# report_name         — target Power BI report.
#
# REPORTING CONTROL
# -----------------
# Confirmed underpayment and overpayment measures include only reconciliation rows
# with UNDERPAID or OVERPAID status. REQUIRES_REVIEW rows are excluded from
# confirmed remediation totals until the underlying evidence is resolved.

import json
import traceback

stage = "bootstrap"

try:
    stage = "import Semantic Link and AuditHero BI dependencies"
    import sempy.fabric as fabric

    from sempy_labs.directlake import (
        generate_direct_lake_semantic_model,
        check_fallback_reason,
    )
    from sempy_labs.tom import connect_semantic_model
    from sempy_labs.report import (
        create_report_from_reportjson,
        update_report_from_reportjson,
        report_rebind,
    )
    from schads_audit.fabric_powerbi import build_audithero_report_json

    stage = "STEP 1 — Define the Lakehouse tables exposed to Power BI"
    print(stage)
    TABLES = {
        "Pay Period Reconciliation": "gold.current_reconciliation",
        "Audit Detail": "gold.current_audit_detail",
        "Rest Break Findings": "gold.current_rest_break_findings",
        "Supplemental Entitlements": "gold.current_event_adjustments",
        "TOIL Findings": "gold.current_toil_findings",
        "Rule Coverage": "ref.rule_coverage",
        "Audit Runs": "ops.audit_runs",
        "Readiness Findings": "ops.readiness_findings",
    }

    stage = "STEP 2 — Create/refresh the Direct Lake semantic model"
    print(stage)
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

    stage = "STEP 3 — Define payroll/audit business measures"
    print(stage)
    MEASURES = {
        "Pay Period Reconciliation": {
            "Employees Audited": ("DISTINCTCOUNT('Pay Period Reconciliation'[employee_id])", "0", "Distinct employees in the current successful audit snapshot."),
            "Pay Periods": ("COUNTROWS('Pay Period Reconciliation')", "0", "Employee pay periods audited in the current snapshot."),
            "Underpaid Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"UNDERPAID\")", "0", "Pay periods with a definite negative actual-minus-expected variance and no unresolved review condition."),
            "Overpaid Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"OVERPAID\")", "0", "Pay periods with a definite positive actual-minus-expected variance and no unresolved review condition."),
            "Requires Review Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"REQUIRES_REVIEW\")", "0", "Pay periods requiring evidence review before a definitive decision."),
            "Actual Pay Unavailable Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"ACTUAL_PAY_UNAVAILABLE\")", "0", "Expected entitlement exists but usable actual payroll earnings were not available."),
            "Compliant Periods": ("CALCULATE(COUNTROWS('Pay Period Reconciliation'), 'Pay Period Reconciliation'[status] = \"COMPLIANT\")", "0", "Pay periods within tolerance and with no unresolved review finding."),
            "Potential Underpayment": ("SUMX(FILTER('Pay Period Reconciliation', 'Pay Period Reconciliation'[status] = \"UNDERPAID\"), -'Pay Period Reconciliation'[variance_actual_minus_expected])", "$#,##0.00;($#,##0.00)", "Underpayment variance for definitive UNDERPAID periods."),
            "Potential Overpayment": ("SUMX(FILTER('Pay Period Reconciliation', 'Pay Period Reconciliation'[status] = \"OVERPAID\"), 'Pay Period Reconciliation'[variance_actual_minus_expected])", "$#,##0.00;($#,##0.00)", "Overpayment variance for definitive OVERPAID periods."),
            "Expected Pay": ("SUM('Pay Period Reconciliation'[expected_amount])", "$#,##0.00;($#,##0.00)", "Sum of expected auditable pay."),
            "Actual Auditable Pay": ("SUM('Pay Period Reconciliation'[actual_auditable_amount])", "$#,##0.00;($#,##0.00)", "Sum of payroll earnings mapped into actual auditable pay."),
            "Net Variance": ("SUM('Pay Period Reconciliation'[variance_actual_minus_expected])", "$#,##0.00;($#,##0.00)", "Actual auditable pay minus expected pay."),
            "Compliance Rate": ("DIVIDE([Compliant Periods], [Pay Periods] - [Requires Review Periods] - [Actual Pay Unavailable Periods])", "0.0%", "Compliance rate among periods with a definitive decision."),
        },
        "Audit Detail": {
            "Shifts Audited": ("COUNTROWS('Audit Detail')", "0", "Shift-level audit records in the current snapshot."),
            "Review Shifts": ("CALCULATE(COUNTROWS('Audit Detail'), 'Audit Detail'[entitlement_status] = \"REQUIRES_REVIEW\")", "0", "Shift records requiring evidence or rule review."),
            "Expected Shift Entitlements": ("SUM('Audit Detail'[expected_amount])", "$#,##0.00;($#,##0.00)", "Expected shift-level Award comparator before pay-period reconciliation."),
        },
        "Rest Break Findings": {
            "Rest Intervals Assessed": ("COUNTROWS('Rest Break Findings')", "0", "Rest intervals assessed between successive AuditHero work units."),
            "Short Rest Findings": ("CALCULATE(COUNTROWS('Rest Break Findings'), 'Rest Break Findings'[rest_shortfall_hours] > 0)", "0", "Intervals shorter than the effective-dated rest requirement."),
            "Rest Findings Requiring Review": ("CALCULATE(COUNTROWS('Rest Break Findings'), 'Rest Break Findings'[status] = \"REQUIRES_REVIEW\")", "0", "Rest findings that require agreement, instruction, release, roster or historical evidence review."),
            "Overtime Rest Cases": ("CALCULATE(COUNTROWS('Rest Break Findings'), 'Rest Break Findings'[overtime_rest_rule_applies] = TRUE())", "0", "Rest intervals where the rest-after-overtime rule applies."),
            "Double-Time Repriced Hours": ("SUM('Rest Break Findings'[double_time_repriced_hours])", "0.00", "Observed resumed-work hours repriced under the applicable rest-after-overtime rule."),
            "Double-Time Top-up": ("SUM('Rest Break Findings'[double_time_topup])", "$#,##0.00;($#,##0.00)", "Evidence-backed top-up calculated to bring resumed work to the required minimum rate."),
            "Paid Absence Rostered Hours": ("SUM('Rest Break Findings'[paid_absence_rostered_hours])", "0.00", "Rostered ordinary hours identified inside the post-release rest window. These remain subject to payroll/evidence verification where payment cannot be determined safely."),
        },
        "Supplemental Entitlements": {
            "Supplemental Expected Adjustments": ("SUM('Supplemental Entitlements'[expected_adjustment])", "$#,##0.00;($#,##0.00)", "Calculated controlled supplemental entitlements.")
        },
        "TOIL Findings": {
            "Outstanding TOIL Hours": ("SUM('TOIL Findings'[remaining_hours])", "0.00", "Remaining overtime hours in the controlled TOIL register."),
            "TOIL Payment Due": ("SUM('TOIL Findings'[expected_adjustment])", "$#,##0.00;($#,##0.00)", "Calculated payment due for TOIL items with sufficient evidence."),
        },
    }

    with connect_semantic_model(
        dataset=semantic_model_name,
        workspace=workspace_name,
        readonly=False,
    ) as tom:
        for table_name, measures in MEASURES.items():
            table = tom.model.Tables[table_name]
            existing = {measure.Name: measure for measure in table.Measures}
            for name, (expression, format_string, description) in measures.items():
                if name in existing:
                    measure = existing[name]
                    measure.Expression = expression
                    measure.FormatString = format_string
                    measure.Description = description
                    measure.DisplayFolder = "AuditHero KPIs"
                else:
                    tom.add_measure(
                        table_name=table_name,
                        measure_name=name,
                        expression=expression,
                        format_string=format_string,
                        description=description,
                        display_folder="AuditHero KPIs",
                    )

    stage = "STEP 4 — Create or update the Power BI report"
    print(stage)
    report_json = build_audithero_report_json()
    reports = fabric.list_reports(workspace=workspace_name)
    name_column = (
        "Name"
        if "Name" in reports.columns
        else "Report Name"
        if "Report Name" in reports.columns
        else None
    )
    exists = bool(name_column and (reports[name_column] == report_name).any())

    if exists:
        update_report_from_reportjson(
            report=report_name,
            report_json=report_json,
            workspace=workspace_name,
        )
    else:
        create_report_from_reportjson(
            report=report_name,
            dataset=semantic_model_name,
            report_json=report_json,
            workspace=workspace_name,
        )

    stage = "STEP 4B — Rebind report to the AuditHero semantic model"
    print(stage)
    report_rebind(
        report=report_name,
        dataset=semantic_model_name,
        report_workspace=workspace_name,
        dataset_workspace=workspace_name,
    )

    stage = "STEP 5 — Check Direct Lake fallback state"
    print(stage)
    fallback = check_fallback_reason(semantic_model_name, workspace=workspace_name)
    display(fallback)
    if "FallbackReasonID" in fallback.columns and (fallback["FallbackReasonID"] != 0).any():
        print(
            "WARNING: one or more tables report a Direct Lake fallback reason. "
            "Review the affected table before production use."
        )
    else:
        print("Direct Lake model and Power BI report deployed successfully.")

except Exception as exc:
    payload = {
        "status": "ERROR",
        "stage": stage,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc()[-12000:],
    }
    print("AUDITHERO BUILD BI FAILED")
    print(json.dumps(payload, indent=2, default=str))
    notebookutils.notebook.exit(
        "AUDITHERO_ERROR:" + json.dumps(payload, default=str)
    )

else:
    notebookutils.notebook.exit(
        "AUDITHERO_SUCCESS:"
        + json.dumps(
            {
                "status": "SUCCESS",
                "semantic_model": semantic_model_name,
                "report": report_name,
            }
        )
    )
