# Historical audit runbook

## Purpose

A historical audit must reconstruct the employment facts and Award version that applied at the time. Do not apply the current SCHADS rate to old shifts.

## Recommended rollout

### 1. One employee / one pay period
Verify classification, employment type, roster mapping, timesheet mapping, pay categories and expected calculation evidence.

### 2. One representative month
Include casual/permanent employees and, where available, weekday, Saturday, Sunday, public holiday, minimum engagement, overtime and sleepover cases.

### 3. Cross a rule boundary
Test at least one pay period around a July annual rate change and, for sleepovers, the June 2026 rule change.

### 4. Twelve months
Review exception patterns and missing mappings.

### 5. Full date range
Only after the smaller samples reconcile.

## Running a multi-year audit

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

The Employment Hero connector chunks large timesheet and roster requests month-by-month while preserving one `audit_run_id` for the final run.

## Rate coverage

- SACS: automated packs from July 2022.
- Home Care employee — disability care: automated packs from July 2024.
- Unsupported historical classification families are `REQUIRES_REVIEW` rather than silently mapped to the wrong wage table.

## Overtime evidence

Historical full-time overtime is materially stronger when roster history is available. AuditHero pulls Employment Hero rostered shifts and matches them to timesheets. Where a full-time timesheet cannot be uniquely tied to a roster, overtime remains a review finding.

PT/casual >38-hour weekly and >76-hour fortnightly thresholds are detected. Where precise allocation across weekend/public-holiday/shiftwork entitlements is ambiguous, AuditHero flags the affected period instead of applying overlapping multipliers mechanically.

## Re-running an audit

Audit runs are append-only. Re-running the same window produces a new `audit_run_id`; the dashboard's latest views select the newest successful run for that audit window.
