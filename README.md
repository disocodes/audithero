# AuditHero — SCHADS payroll compliance on Databricks

AuditHero is an effective-dated payroll audit platform for **SCHADS / MA000100**. It uses Employment Hero as the operational payroll/time source and Databricks for ingestion, award-rule calculation, historical reconciliation, monthly workflow orchestration and AI/BI reporting.

It supports two operating modes:

1. **Historical audit** — pull Employment Hero data programmatically for a specified date range and recalculate historical entitlements using the rule/rate version applicable to the pay period.
2. **Monthly payroll assurance** — pull recent timesheets, rosters and draft/final payroll, calculate expected entitlements, compare actual pay, refresh the Databricks dashboard and send the dashboard snapshot to Accounts.

## Current architecture

```text
Employment Hero HR API
  employees + histories + pay details
  timesheets + rostered shifts
             |
Employment Hero Payroll API
  pay runs + earnings lines
             |
             v
Databricks / Unity Catalog
  silver normalized evidence
             |
Effective-dated SCHADS JSON library
  rates + conditions + allowances
             |
Entitlement engines
  ordinary/weekend/PH/shiftwork
  roster/daily overtime
  supplemental entitlements
             |
  gold.audit_detail
  gold.audit_event_adjustments
  gold.pay_period_reconciliation
             |
Databricks AI/BI dashboard
             |
Monthly dashboard snapshot -> Accounts
```

## Rule library

Award logic is source-controlled data, not one enormous notebook:

```text
rules/MA000100/
  manifest.json
  rates/
    2022-07-01_sacs.json
    2023-07-01_sacs.json
    2023-07-01_home_care_disability.json
    2024-07-01_sacs.json
    2024-07-01_home_care_disability.json
    2025-07-01_sacs.json
    2025-07-01_home_care_disability.json
    2026-07-01_sacs.json
    2026-07-01_home_care_disability.json
  conditions/
    2022-07-01.json
    ...
    2026-06-01.json
    2026-07-01.json
  allowances/
    2022-07-01.json
    ...
    2026-07-01.json
```

The rule selector uses the **pay-period start** when available, because Award variations can apply from the first full pay period starting on or after the operative date.

## Automated coverage

The engine currently covers:

- effective-dated SACS rates from July 2022;
- Home Care employee — disability care rates from July 2023;
- historical employment type and classification history;
- casual loading;
- Saturday, Sunday and public-holiday ordinary penalties;
- afternoon/night shift loadings;
- minimum engagement;
- state-wide public holidays plus controlled overrides;
- Employment Hero roster matching;
- full-time overtime outside a uniquely matched roster;
- PT/casual daily overtime where allocation is unambiguous;
- 38-hour weekly and 76-hour fortnightly overtime threshold detection;
- sleepover allowance and the June 2026 sleepover rule boundary;
- on-call allowance;
- recall to workplace;
- active work during sleepover;
- remote work minimums;
- controlled broken-shift allowance facts;
- higher duties;
- controlled 24-hour-care calculations;
- actual-versus-expected pay-period reconciliation.

Complex or incomplete situations become `REQUIRES_REVIEW` rather than being guessed.

## Quick deployment

Read **[QUICKSTART.md](QUICKSTART.md)** first.

```bash
git clone https://github.com/disocodes/audithero.git
cd audithero

databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
# Optional: Accounts workspace user/email; defaults to the deployer.
export DATABRICKS_BUNDLE_VAR_accounts_email="payroll@your-company.example"

./scripts/deploy.sh
./scripts/configure_secrets.sh
```

Then complete the tenant mappings in `config/`, test the Employment Hero connection, and validate one month before running a multi-year audit.

## Monthly Accounts workflow

The monthly job is deployed **PAUSED intentionally**. When enabled it:

```text
Pull recent Employment Hero evidence
        -> run SCHADS entitlement audit
        -> reconcile actual payroll
        -> refresh AI/BI dashboard
        -> email dashboard snapshot to Accounts
```

The default cadence is 09:00 on the 25th in `Australia/Perth` with a 45-day lookback. Change the cron to align with your payroll cycle.

## Supplemental evidence

Some facts are not safely inferable from a normal timesheet. Controlled items such as recall, active sleepover work and broken-shift evidence can be supplied through:

`/Volumes/<catalog>/bronze/landing/supplemental_events.csv`

See **[docs/SUPPLEMENTAL_EVENTS.md](docs/SUPPLEMENTAL_EVENTS.md)**.

## Historic audit example

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

For SACS and Home Care disability employees, the repository now contains effective-dated wage rates throughout that three-year window. Other unsupported SCHADS wage families fail closed until verified packs are added.

## Validation principle

Do not remediate wages from an unvalidated first run. Verify Award coverage, employee classification history, employment type, work-group mapping, pay-category mapping and representative manual calculations before acting on historical totals.

This repository is a compliance-engineering solution, not legal advice.
