# Monthly payroll runbook

The objective is to audit payroll **before finalisation**, not merely discover mistakes after payment.

## Suggested process

1. Managers approve timesheets.
2. Payroll creates/imports the draft pay run in Employment Hero Payroll.
3. Run `AuditHero - Monthly Payroll Audit`.
4. Accounts opens the Databricks AI/BI dashboard.
5. Resolve `REQUIRES_REVIEW` first.
6. Confirm underpayments against shift evidence and Award source.
7. Investigate overpayments; do not automate employee deductions.
8. Correct the draft payroll.
9. Re-run AuditHero.
10. Finalise payroll only after exceptions are resolved or formally documented.

The default scheduled job uses a **45-day lookback**, making it tolerant of weekly, fortnightly and monthly pay calendars. Change the schedule to match your organisation.

The bundle deploys the schedule **PAUSED** so an unvalidated rule configuration cannot start issuing compliance findings automatically.
