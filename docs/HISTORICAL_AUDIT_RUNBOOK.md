# Historical audit runbook

## Purpose

A historical audit must reconstruct the employment facts and Award version that applied at the time. Do not apply the current SCHADS rate to old shifts.

## Recommended rollout

### 1. One employee / one pay period
Verify classification, employment type, roster mapping, timesheet mapping, pay categories, work location and expected calculation evidence.

### 2. One representative month
Include casual/permanent employees and, where available, weekday, Saturday, Sunday, public holiday, minimum engagement, overtime, broken-shift and sleepover cases.

### 3. Cross a rule boundary
Test at least one pay period around a July annual rate change and, for sleepovers, the June 2026 rule change.

### 4. Twelve months
Review exception patterns, local/public-holiday mappings and missing evidence.

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
- Home Care employee — disability care: automated packs from July 2023.
- Unsupported historical classification families are `REQUIRES_REVIEW` rather than silently mapped to the wrong wage table.

## Overtime evidence

Historical full-time overtime is materially stronger when roster history is available. AuditHero pulls Employment Hero rostered shifts and matches them to timesheets. Where a full-time timesheet cannot be uniquely tied to a roster, overtime remains a review finding.

For part-time/casual employees, AuditHero now automatically reprices excess hours above the 38-hour weekly or 76-hour fortnightly threshold where the crossing can be uniquely allocated to a specific trailing part of a shift. It does **not** stack a second overtime calculation where daily/roster overtime has already repriced the same hours. Conflicting weekly/fortnightly allocations remain `REQUIRES_REVIEW`.

Useful flags:

- `WEEKLY_FORTNIGHTLY_OVERTIME_ALLOCATION_CONFLICT`
- `PERIOD_OVERTIME_OVERLAPS_DAILY_OR_ROSTER_OVERTIME`
- `PERIOD_OVERTIME_ALLOCATION_REVIEW`
- `CROSS_MIDNIGHT_OVERTIME_ALLOCATION_REVIEW`

## Broken shifts

AuditHero groups separate same-day disability/home-care work periods when there is a genuine unpaid gap and can automatically apply:

- one-break or two-break broken-shift allowance;
- PT/casual minimum engagement for each work period;
- review controls for more than two unpaid breaks;
- review controls for two-break agreement evidence;
- 12-hour span rules where the applicable period rate is unambiguous.

Important review flags include:

- `TWO_BREAK_BROKEN_SHIFT_AGREEMENT_VERIFY`
- `BROKEN_SHIFT_MORE_THAN_TWO_BREAKS`
- `BROKEN_SHIFT_12H_OVERTIME_INTERACTION_REVIEW`
- `BROKEN_SHIFT_MINIMUM_MULTIRATE_REVIEW`

## Sleepovers

An explicit sleepover record is treated as a sleepover span and allowance — **not eight ordinary worked hours**. Active work during the sleepover belongs in a separate overtime/supplemental event.

Adjacent work can be grouped as `BEFORE`, `SLEEPOVER`, and `AFTER`. The effective-dated condition pack determines whether the pre/post work is treated under the pre-June-2026 model or the continuous-shift rules introduced from the 2026 variation.

Review flags can include:

- `SLEEPOVER_CONTINUOUS_SHIFT_OVERTIME_EXCESS:*`
- `SLEEPOVER_BEFORE_MORE_THAN_8H`
- `SLEEPOVER_AFTER_MORE_THAN_8H`
- `SLEEPOVER_MINIMUM_MULTIRATE_REVIEW`

## Public holidays and location

Statewide holidays apply by state. Local/substituted overrides may include `holiday_location_key`; these are applied only to timesheets mapped to the same key. This prevents a local holiday in one location from being incorrectly applied to all employees in the state.

Before a multi-year audit, run:

```bash
databricks bundle run audit_readiness
```

Review `WORK_LOCATION` findings and configure local holiday keys where relevant.

## Review order

For remediation work, review in this order:

1. `REQUIRES_REVIEW`
2. confirmed `UNDERPAID`
3. confirmed `OVERPAID`
4. `COMPLIANT`

A numerical variance on a `REQUIRES_REVIEW` record must not be treated as a remediation amount until the missing/ambiguous evidence is resolved.

## Re-running an audit

Audit runs are append-only. Re-running the same window produces a new `audit_run_id`; the dashboard's latest views select the newest successful run for that audit window.
