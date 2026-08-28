# Microsoft Fabric architecture

```text
Employment Hero HR API + Payroll API
              |
              v
     Fabric Data Factory Pipelines
              |
              v
     Fabric Runtime 2.0 Environment
              |
              v
         Fabric Notebooks
              |
              v
     Schema-enabled Lakehouse
   bronze / silver / ref / gold / ops
              |
              v
      materialised gold.current_*
              |
              v
   Direct Lake semantic model
              |
              v
         Power BI report
```

## Lakehouse schemas

- `bronze` — landing/control files and raw-compatible evidence.
- `silver` — canonical employees, pay details, employment history, rosters, timesheets, payroll earnings and holidays.
- `ref` — effective-dated SCHADS rates, conditions, allowances and source metadata.
- `gold` — audit detail, supplemental adjustments, TOIL findings and pay-period reconciliation.
- `ops` — audit runs, readiness findings and deployment/runtime checks.

## Why materialised `gold.current_*` tables

The audit tables are append-only by `audit_run_id`. The BI notebook materialises latest-successful snapshots into physical Delta tables so the Direct Lake semantic model can query OneLake efficiently without relying on SQL views.

## Shared engine boundary

Fabric-specific code handles:

- NotebookUtils/Key Vault secrets
- Lakehouse writes
- Fabric REST deployment
- Fabric pipelines/schedules
- Direct Lake/Power BI

SCHADS interpretation and arithmetic remain in the shared `schads_audit` package used by both platforms.