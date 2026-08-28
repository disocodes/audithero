# AuditHero — SCHADS payroll auditing on Databricks

AuditHero audits Employment Hero timesheets/payroll against effective-dated **SCHADS Award (MA000100)** rules using Databricks. It supports both **ongoing monthly payroll assurance** and **multi-year historical audits**.

## What this repository gives you

- Employment Hero HR API connector for employees, historical employment type, historical pay/classification details and date-range timesheets.
- Employment Hero Payroll API connector for pay runs and earnings lines when your tenant exposes it.
- Effective-dated SCHADS rule packs as JSON rather than hard-coded notebook logic.
- SACS rate packs for 1 July 2022, 2023, 2024, 2025 and 2026.
- Historical allowance packs and condition packs.
- A separate 1 June 2026 condition version for the SCHADS sleepover changes.
- Deterministic expected-pay calculation with calculation evidence.
- Actual-vs-expected reconciliation by **employee + pay period**.
- `COMPLIANT`, `UNDERPAID`, `OVERPAID`, `REQUIRES_REVIEW`, and entitlement-only outcomes.
- Databricks Declarative Automation Bundle jobs for setup, historical auditing, connection testing and monthly auditing.
- A Databricks AI/BI dashboard resource — Power BI is not required.
- Regression tests and GitHub Actions.

## Architecture

```text
Employment Hero HR API             Employment Hero Payroll API
 employees                           pay runs / earnings lines
 employment histories
 pay-detail/classification history
 date-range timesheets
          \                           /
           +------ Databricks -------+
                  Silver Delta
                       |
              SCHADS JSON library
                       |
                Entitlement engine
                       |
              gold.audit_detail
                       |
            pay-period reconciliation
                       |
       gold.pay_period_reconciliation
                       |
             Databricks AI/BI
                       |
              Payroll / Accounts
```

## Start here

Read **[QUICKSTART.md](QUICKSTART.md)**. The intended sequence is:

1. deploy the bundle;
2. configure Employment Hero secrets;
3. map classifications, pay categories and work locations;
4. run a one-month validation sample;
5. run your multi-year historical audit;
6. unpause the monthly job only after validation.

## Rule library

```text
rules/MA000100/
  manifest.json
  rates/
    2022-07-01_sacs.json
    2023-07-01_sacs.json
    2024-07-01_sacs.json
    2025-07-01_sacs.json
    2026-07-01_sacs.json
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

A July wage change does **not** require rewriting a notebook. Add a JSON rate pack and tests, update the manifest, then rerun setup.

## Historical date-range audits

The HR connector uses Employment Hero's documented wildcard employee ID `-` for all-employee timesheet retrieval and chunks large history requests by month. Classification and employment type are independently effective-dated using the employee's Pay Details and Employment History APIs.

## Important safety behavior

AuditHero **fails closed**. Missing classification mapping, unknown historical employment type, missing work location, incomplete sleepover facts, unmapped pay categories, complex overtime overlap and other ambiguous conditions become `REQUIRES_REVIEW` rather than a guessed compliance result.

## Current automated coverage

The supplied wage-rate packs automate the **SACS classification family** from July 2022 onward. The engine handles common casual loading, weekend/public-holiday penalties, weekday shift loadings, minimum engagement, cross-midnight shifts, simple daily overtime, sleepover allowance, state-wide public holidays, and pay-period reconciliation.

Home Care/Aged Care/other SCHADS wage families can be added as additional canonical rate packs without changing the versioning architecture. Until verified packs are loaded, those employees should remain review items.

## Sources

The rule files include their source URLs. Primary sources include the Fair Work Commission consolidated Award, Fair Work Ombudsman pay guides, Fair Work's 2026 sleepover guidance, Employment Hero API documentation, Employment Hero Payroll API documentation and Databricks bundle documentation.

## Disclaimer

This is a compliance-engineering system, not legal advice. Have payroll/industrial-relations specialists validate Award coverage, classification mappings, source data and interpretation before remediation or recovery decisions.
