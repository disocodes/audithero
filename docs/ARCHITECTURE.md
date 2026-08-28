# Architecture

AuditHero uses a simple Unity Catalog layout:

| Schema | Purpose |
|---|---|
| `bronze` | landing area / future immutable API payload archive |
| `silver` | canonical employee, history, timesheet, payroll and holiday records |
| `ref` | effective-dated SCHADS rates, conditions, allowances and source evidence |
| `gold` | shift entitlement evidence and employee/pay-period reconciliation |
| `ops` | audit run history |

The **shift** is the entitlement-calculation grain. The **employee + pay period** is the primary under/over-payment reconciliation grain. This avoids assuming that Employment Hero exposes a perfect one-to-one relationship between a timesheet and every payroll earning line.

Every audit carries an `audit_run_id`. Historical re-runs are append-only; the BI views select the latest successful run for a matching audit window.
