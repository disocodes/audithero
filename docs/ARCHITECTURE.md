# AuditHero architecture

AuditHero separates source ingestion, canonical payroll evidence, SCHADS calculation, audit persistence and reporting so each layer can be reviewed independently.

```text
Payroll / HR / Timekeeping exports        Optional Employment Hero API
                 |                                   |
                 v                                   v
       Source mapping + conversion             API normalization
                 \                                   /
                  \                                 /
                   v                               v
                    Canonical AuditHero data
                              |
                       Readiness checks
                              |
                              v
                    Shared SCHADS audit engine
                              |
                  Effective-dated MA000100 rules
                              |
             +----------------+----------------+
             |                |                |
        audit detail      event / TOIL    reconciliation
             |                |                |
             +----------------+----------------+
                              |
                     successful audit data
                              |
                +-------------+-------------+
                |                           |
        Microsoft Fabric                Databricks
                |                           |
        Direct Lake model             Gold Delta tables
                |                           |
            Power BI               Unity Catalog metric views
                                            |
                                      +-----+-----+
                                      |           |
                                    AI/BI       Genie
```

## Installation layer

Each platform provides an installer notebook that creates or updates the AuditHero application resources and runs Setup and Self Test. The matching uninstaller removes AuditHero-managed application resources while preserving payroll and audit storage unless permanent deletion is explicitly confirmed.

## Source ingestion and mapping

Source mapping converts organisation-specific CSV/XLSX exports into AuditHero canonical datasets. Mapping configuration identifies source files, sheets, columns, value translations and approved transformations. SCHADS formulas are not stored in source mappings.

Employment Hero API ingestion is an optional alternative to uploaded files. Both ingestion methods feed the same canonical model and calculation engine.

## Canonical evidence layer

The canonical model provides stable structures for employees, employment history, classifications/pay details, timesheets, rosters, payroll earnings and controlled evidence registers. Source-system changes are handled in the ingestion or mapping layer without changing Award calculation rules.

## Shared calculation layer

Fabric and Databricks use the same `schads_audit` Python package and effective-dated rule packs. The engine selects applicable rules from the supplied employee, shift, pay-period and evidence facts and records calculation evidence with the results.

When the available evidence does not support a reliable automated conclusion, the result is recorded for review rather than classified as a definitive underpayment or overpayment.

## Storage and audit trail

### Microsoft Fabric

Fabric stores normalized evidence and audit results in the AuditHero Lakehouse. Latest-successful `gold.current_*` tables provide the reporting snapshot used by Direct Lake and Power BI.

### Databricks

Databricks retains source/canonical files in Unity Catalog Volumes, normalized evidence in Silver Delta tables, audit results in Gold Delta tables and run/readiness records in the `ops` schema.

Each persisted audit result is associated with an audit run so reruns and historical investigations remain traceable.

## Semantic and reporting layer

### Microsoft Fabric

A Direct Lake semantic model exposes AuditHero business measures and the Power BI report.

### Databricks

Unity Catalog metric views under the `semantic` schema define governed payroll and audit measures. The same governed results are available to the AI/BI dashboard and the **AuditHero - Payroll Compliance** Genie space.

Genie is an analysis interface over calculated audit results; SCHADS entitlement calculations are completed by the AuditHero engine before the data reaches the semantic layer.

## Result integrity

Reporting uses successful audit runs. `REQUIRES_REVIEW` remains separate from definitive reconciliation statuses and is excluded from confirmed underpayment and overpayment totals until the relevant evidence is resolved.
