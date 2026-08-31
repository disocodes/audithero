# AuditHero architecture

AuditHero separates installation, source-system conversion, canonical payroll evidence, Award calculation and reporting so each layer can be operated and reviewed independently.

```text
One-time platform installer notebook
              |
              v
Fabric workspace or Databricks workspace
              |
              +--------------------------------------+
              |                                      |
Payroll / HR / Timekeeping exports       Optional Employment Hero API
              |                                      |
              v                                      v
     Source Mapping + Conversion              API normalization
              \                                      /
               \                                    /
                v                                  v
                 Canonical AuditHero datasets
                           |
                    File/API Readiness
                           |
                           v
                 Shared SCHADS audit engine
                           |
             Effective-dated MA000100 rules
                           |
          +----------------+----------------+
          |                |                |
     audit detail     event/TOIL       reconciliation
          |                |                |
          +----------------+----------------+
                           |
                  latest successful data
                           |
               +-----------+-----------+
               |                       |
          Power BI/Fabric        Databricks AI/BI
```

## Installation layer

Each platform has an installer notebook that is run from the platform UI. It creates or updates the AuditHero application resources and runs Setup/Self Test.

The matching uninstaller removes AuditHero-managed application resources. Payroll/audit storage is preserved by default and requires an explicit confirmation before permanent deletion.

## Source mapping layer

This layer knows how the source system names fields. It converts arbitrary CSV/Excel exports to canonical AuditHero datasets and records `mapping_used.json` plus a conversion report. It does not contain SCHADS formulas.

## Canonical evidence layer

The canonical model provides stable employee, employment history, classification/pay details, timesheet, roster, payroll and evidence-register structures. This allows source systems to change without changing the Award engine.

## Shared calculation layer

Both Fabric and Databricks call the same Python modules and effective-dated rule packs. Platform notebooks orchestrate work but do not maintain separate payroll formulas.

## Storage/output layer

Fabric uses a Lakehouse and Databricks uses Unity Catalog/Delta. Both persist detailed evidence and pay-period reconciliation rather than only a dashboard total.

## Reporting layer

Fabric materializes latest-successful `gold.current_*` tables for Direct Lake/Power BI. Databricks exposes latest-successful views/tables to AI/BI. Failed runs should not replace the last successful operator-facing snapshot.

## Fail-closed principle

When an automated allocation would require guessing a material fact, AuditHero records a review finding/status. This keeps unresolved evidence separate from confirmed remediation figures.