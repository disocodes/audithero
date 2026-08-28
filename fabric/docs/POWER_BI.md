# Power BI / Direct Lake

AuditHero Fabric uses an explicit Direct Lake semantic model; it does not depend on Fabric's former automatically-created default semantic models.

## Model tables

The BI build notebook materialises latest-successful audit snapshots and exposes physical Delta tables such as:

- `gold.current_reconciliation`
- `gold.current_audit_detail`
- `gold.current_event_adjustments`
- `gold.current_toil_findings`
- `ref.rule_coverage`
- `ops.readiness_findings`

## Core measures

- Employees Audited
- Pay Periods
- Underpaid Periods
- Overpaid Periods
- Requires Review Periods
- Compliant Periods
- Potential Underpayment
- Potential Overpayment
- Expected Pay
- Actual Auditable Pay
- Net Variance
- Compliance Rate

Potential remediation measures must exclude unresolved `REQUIRES_REVIEW` / instrument-review records.

## Report pages

1. Payroll Overview
2. Exceptions
3. Shift Evidence
4. Supplemental & TOIL
5. Controls & Rule Coverage

The BI notebook creates/updates the semantic model and report programmatically so the BI layer is source-controlled and reproducible.