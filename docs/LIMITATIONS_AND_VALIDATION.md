# Limitations and validation

AuditHero is deliberately conservative.

The supplied historical wage packs automate the **SACS rate family** from July 2022 onward. Other SCHADS wage families require independently verified rate packs.

Several conditions require facts that a basic timesheet cannot reliably prove, including part-time agreed-pattern changes, complex weekly/fortnightly overtime allocation, active work during sleepover, higher duties, remote work, 24-hour care, recall, TOIL, enterprise agreements and individual flexibility arrangements. Those cases are intended to remain review items until the required evidence/module is added.

Gross payroll must not be compared blindly against worked-time entitlements because leave, bonuses and reimbursements can mask an underpayment. `pay_category_mapping.json` controls which actual earnings are auditable.

Before remediation, manually reconcile representative cases and obtain competent payroll/industrial-relations review of Award coverage, classification, assumptions and interpretation.
