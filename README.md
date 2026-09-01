# AuditHero

AuditHero is a payroll audit solution for the **Social, Community, Home Care and Disability Services Industry Award 2010 (SCHADS / MA000100)**. It reconstructs expected Award entitlements from employment, roster and timekeeping evidence, compares expected pay with payroll where actual earnings are supplied, and separates definitive reconciliation results from items requiring human review.

AuditHero runs in **Microsoft Fabric** or **Databricks**. Installation and routine operation are available from the platform UI; command-line deployment is available for administrators and CI/CD.

> AuditHero is compliance-support software, not legal advice. Validate Award coverage, classifications, historical industrial instruments and representative calculations before using results for remediation, recovery or payroll-change decisions.

## Install AuditHero

Each platform uses a bootstrap installer notebook for the first installation. The bootstrap also installs managed **Install or Upgrade** and **Uninstall** notebooks for later administration.

### Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates the Lakehouse, Environment, AuditHero notebooks, Data Factory pipelines, schedule, Direct Lake semantic model and Power BI report, then runs Setup and Self Test.

See [Install AuditHero in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md).

### Databricks

In **Workspace → Import → URL**, import the raw GitHub URL for `installers/Databricks_Install_AuditHero.py`, open it and choose **Run all**.

The installer creates or updates the AuditHero workspace files, Jobs, Unity Catalog structures, AI/BI dashboard, governed metric views and **AuditHero - Payroll Compliance** Genie space, then runs Setup and Self Test. Administration notebooks are installed under `/Shared/AuditHero/admin`.

See [Install AuditHero in Databricks](docs/INSTALL_DATABRICKS_UI.md).

Employment Hero credentials are **not** required for either installation method or for uploaded-file auditing.

## Upgrade or uninstall

After installation, use the managed administration notebooks.

**Microsoft Fabric**

- `AuditHero - Install or Upgrade`
- `AuditHero - Uninstall`

**Databricks**

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

A standard uninstall preserves payroll and audit storage. Permanent data deletion requires the explicit confirmation phrase `DELETE AUDITHERO DATA` inside the uninstaller notebook.

## CSV / Excel audit workflow

For source exports with organisation-specific fields:

1. Upload the original CSV/XLSX exports from payroll, HR, rostering and timekeeping systems.
2. Run **AuditHero - Build Source Mapping Workbook**.
3. Review `source_mapping_draft.xlsx` and confirm the source-to-AuditHero field mappings.
4. Save the approved workbook as `source_mapping.xlsx`.
5. Run **AuditHero - Convert Mapped Files and Run Audit** for the required audit dates.
6. Review the results in **Power BI** on Fabric or **AI/BI and Genie** on Databricks.

The combined workflow performs:

```text
Raw CSV/XLSX exports
        ↓
Approved source_mapping.xlsx
        ↓
Canonical conversion
        ↓
File Readiness
        ↓
SCHADS audit
        ↓
Reporting refresh
```

Run **AuditHero - Convert Source Files** separately when conversion and readiness need to be reviewed before payroll calculation.

If the source data already uses the AuditHero canonical workbook/CSV format, the mapping stage can be skipped and the canonical uploaded-file audit can be run directly.

## Platform comparison

| | Microsoft Fabric | Databricks |
|---|---|---|
| Operating surface | Fabric workspace + Data Factory pipelines | Jobs & Pipelines + Catalog Explorer |
| File storage | Lakehouse Files | Unity Catalog Volumes |
| Reporting | Direct Lake + Power BI | AI/BI + Unity Catalog metric views + Genie |
| One-notebook first installation | Yes | Yes |
| Managed upgrade notebook | Yes | Yes |
| Managed uninstall notebook | Yes | Yes |
| CSV/Excel field mapping | Yes | Yes |
| Employment Hero API | Optional | Optional |
| CLI required | No | No |

## Data sources

### Uploaded files

AuditHero accepts:

- organisation-specific CSV/XLSX exports converted through the source-mapping workflow;
- a canonical workbook named `audithero_input.xlsx`; or
- separate canonical CSV/Excel files.

Minimum audit data includes:

- employees;
- effective-dated pay/classification details;
- employment history; and
- timesheets.

Rostered shifts, pay runs and payroll earnings are recommended because they improve overtime analysis and actual-versus-expected reconciliation. Historical instrument coverage, part-time patterns and other controlled evidence can be supplied in the same workbook or as separate mapped datasets.

See [Audit data requirements](docs/AUDIT_DATA_REQUIREMENTS.md) and [Importing and mapping CSV/Excel files](docs/IMPORT_AND_FIELD_MAPPING.md).

### Employment Hero API

Employment Hero HR and Payroll API connectivity can be enabled for direct extraction and recurring audits. It is not required for installation or uploaded-file audits.

## What AuditHero checks

The shared calculation engine uses effective-dated SCHADS rule packs and supports the automated controls implemented by this project, including ordinary penalties, casual loading, minimum engagement, roster/daily/period overtime, broken shifts, sleepovers, public holidays, shiftwork, part-time pattern controls, rest-after-overtime, meal events, supplemental events, TOIL and industrial-instrument coverage checks.

Where the supplied evidence does not support a reliable automated conclusion, AuditHero records **`REQUIRES_REVIEW`**. Review items are excluded from confirmed remediation totals until resolved.

See [SCHADS rules and evidence](docs/SCHADS_RULES_AND_EVIDENCE.md).

## Result statuses

Typical pay-period results are:

- `COMPLIANT` — actual auditable pay is within tolerance of expected pay and no unresolved review condition prevents the conclusion;
- `UNDERPAID` — confirmed auditable pay is below expected pay;
- `OVERPAID` — confirmed auditable pay is above expected pay;
- `REQUIRES_REVIEW` — evidence or rule allocation is not reliable enough for an automated conclusion; and
- `ACTUAL_PAY_UNAVAILABLE` — expected entitlements were calculated but usable payroll earnings were not supplied.

See [Understanding AuditHero results](docs/UNDERSTANDING_RESULTS.md).

## Documentation

Start at [Documentation home](docs/README.md). Main guides include:

- [Quick start](QUICKSTART.md)
- [Install in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md)
- [Install in Databricks](docs/INSTALL_DATABRICKS_UI.md)
- [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](docs/RUNNING_AUDITS.md)
- [Understanding results](docs/UNDERSTANDING_RESULTS.md)
- [SCHADS rules and evidence](docs/SCHADS_RULES_AND_EVIDENCE.md)
- [Notebook reference](docs/NOTEBOOK_REFERENCE.md)
- [Administration and security](docs/ADMINISTRATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Optional CLI and automation](docs/CLI_AND_AUTOMATION.md)

## Administration

The effective-dated Award rule library is stored under `rules/MA000100/`. Fabric and Databricks use the same `schads_audit` Python package and rule packs so payroll calculation logic remains consistent across platforms.

The installed administration notebooks are the primary UI path for setup, upgrade and removal. CLI scripts, REST deployment tooling and CI/CD remain available for automated administration.
