# Monthly payroll audit runbook

## Objective

Run AuditHero while payroll is still reviewable. The system is intended as a payroll assurance control, not merely a report produced after payment.

## Recommended sequence

1. Managers approve timesheets/rosters in Employment Hero.
2. Payroll prepares the draft pay run.
3. AuditHero pulls the recent HR/time/roster data and Payroll earnings lines.
4. AuditHero recalculates expected SCHADS entitlements.
5. Accounts opens the AI/BI **Exceptions** page.
6. Resolve `REQUIRES_REVIEW` before relying on a dollar variance.
7. Confirm underpayments and correct the draft payroll.
8. Investigate overpayments; do not automatically deduct them from future wages.
9. Re-run AuditHero after corrections where appropriate.
10. Finalise payroll and retain the audit run/evidence.

## Scheduled job

`AuditHero - Monthly Payroll Audit`

Defaults:
- 25th day of the month
- 09:00 Australia/Perth
- 45-day lookback
- schedule deployed PAUSED until validation

After the audit task succeeds, a Databricks dashboard task refreshes the AI/BI dashboard and sends a snapshot to the configured `accounts_email` subscriber. The variable defaults to the Databricks deployer and should normally be overridden to the responsible Accounts/Payroll workspace user.

## Why a 45-day lookback?

It safely overlaps common weekly, fortnightly and monthly payroll cycles. Pay-run boundaries, not the lookback window itself, drive the reconciliation grain.

## Review priority

1. `REQUIRES_REVIEW`
2. `UNDERPAID`
3. `OVERPAID`
4. `COMPLIANT`

A `REQUIRES_REVIEW` status intentionally blocks a false remediation amount where evidence is incomplete.

## Supplemental events

Where a payroll fact is not represented by an ordinary timesheet—such as on-call, recall, active sleepover work or a verified broken shift—load the controlled event row before the run. Review `docs/SUPPLEMENTAL_EVENTS.md`.
