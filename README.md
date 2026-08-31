# AuditHero

AuditHero is a payroll audit solution for the **Social, Community, Home Care and Disability Services Industry Award 2010 (SCHADS / MA000100)**. It reconstructs expected Award entitlements from employment, roster and timekeeping evidence, compares expected pay with payroll where actual earnings are supplied, and clearly separates confirmed results from items that still need human review.

AuditHero runs in **Microsoft Fabric** or **Databricks**. Installation and normal operation are designed to happen from the platform UI. Command-line deployment remains available for administrators who prefer automation, but it is not required.

> AuditHero is compliance-support software, not legal advice. Validate Award coverage, classifications, historical industrial instruments and representative calculations before using results for remediation, recovery or payroll-change decisions.

## Install AuditHero

Each platform has a single bootstrap installer notebook.

### Microsoft Fabric

Download and import:

`installers/Fabric_Install_AuditHero.py`

Open it in the target Fabric workspace and choose **Run all**. The notebook detects the current workspace and creates or updates the Lakehouse, Environment, AuditHero notebooks, Data Factory pipelines, schedule, Direct Lake semantic model and Power BI report. It also runs Setup and Self Test.

See [Install AuditHero in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md).

### Databricks

From the Databricks Workspace **Import** dialog, import the public raw URL for:

`installers/Databricks_Install_AuditHero.py`

Open the notebook and choose **Run all**. It installs the AuditHero workspace files and notebooks, selects or creates the SQL warehouse used by AI/BI, creates or updates the AuditHero jobs/dashboard, then runs Setup and Self Test.

See [Install AuditHero in Databricks](docs/INSTALL_DATABRICKS_UI.md).

Employment Hero credentials are **not** required for either installation method or for uploaded-file auditing.

## Uninstall AuditHero

Matching uninstaller notebooks are provided:

- `installers/Fabric_Uninstall_AuditHero.py`
- `installers/Databricks_Uninstall_AuditHero.py`

A normal uninstall removes AuditHero application resources but preserves payroll/audit data. Permanent data deletion requires the explicit confirmation phrase `DELETE AUDITHERO DATA` inside the uninstaller notebook.

## The normal operator workflow

Most organisations do **not** need to reshape their payroll exports before using AuditHero.

1. Upload the original CSV/Excel exports from payroll, HR, rostering and timekeeping systems.
2. Run **AuditHero - Build Source Mapping Workbook**.
3. Open the generated Excel mapping workbook and confirm which source fields feed the AuditHero fields.
4. Save the approved workbook as `source_mapping.xlsx`.
5. Run **AuditHero - Convert Mapped Files and Run Audit**.
6. Review results in **Power BI** (Fabric) or **Databricks AI/BI**.

The combined pipeline/job performs the repetitive work after the mapping is approved:

```text
Raw CSV/XLSX exports
        ↓
Approved source_mapping.xlsx
        ↓
Convert to AuditHero canonical datasets
        ↓
File Readiness checks
        ↓
SCHADS audit
        ↓
Dashboard refresh
```

You can run **AuditHero - Convert Source Files** separately when you want to inspect converted data and readiness results before calculating payroll.

If your files already use the AuditHero canonical workbook/CSV format, skip the mapping/conversion stages and run the uploaded-file audit directly.

## Choose your platform

| | Microsoft Fabric | Databricks |
|---|---|---|
| Normal operating surface | Fabric workspace + Data Factory pipelines | Jobs & Pipelines / Workflows |
| File storage | Lakehouse Files | Unity Catalog Volumes |
| Reporting | Direct Lake + Power BI | Databricks AI/BI |
| One-notebook installation | Yes | Yes |
| One-notebook uninstall | Yes | Yes |
| CSV/Excel field mapping | Yes | Yes |
| Employment Hero API | Optional | Optional |
| CLI required | No | No |

## Data sources

### Uploaded files — easiest place to start

AuditHero accepts:

- arbitrary CSV/XLSX exports converted through the field-mapping workflow;
- one canonical workbook named `audithero_input.xlsx`; or
- separate canonical CSV/Excel files.

The minimum audit data is:

- employees;
- effective-dated pay/classification details;
- employment history; and
- timesheets.

Rostered shifts, pay runs and payroll earnings are recommended because they improve overtime analysis and actual-versus-expected reconciliation. Historical instrument coverage, part-time patterns and other controlled evidence can be supplied in the same workbook or as separate mapped datasets.

See [Audit data requirements](docs/AUDIT_DATA_REQUIREMENTS.md) and [Importing and mapping CSV/Excel files](docs/IMPORT_AND_FIELD_MAPPING.md).

### Employment Hero API — optional automation

Employment Hero HR and Payroll API connectivity can be enabled later. It is not required to install AuditHero or run uploaded-file audits. API mode is useful when an organisation wants automatic extraction and recurring audits without manually uploading exports.

## What AuditHero checks

The shared calculation engine uses effective-dated SCHADS rule packs and supports the automated controls implemented by this project, including ordinary penalties, casual loading, minimum engagement, roster/daily/period overtime, broken shifts, sleepovers, public holidays, shiftwork, part-time pattern controls, rest-after-overtime, meal events, supplemental events, TOIL and industrial-instrument coverage checks.

Where the available evidence does not support a reliable automated conclusion, AuditHero uses **`REQUIRES_REVIEW`** rather than guessing. Review items are excluded from confirmed remediation totals.

See [SCHADS rules and evidence](docs/SCHADS_RULES_AND_EVIDENCE.md).

## Result statuses

Typical pay-period results are:

- `COMPLIANT` — actual auditable pay is within tolerance of expected pay;
- `UNDERPAID` — confirmed auditable pay is below expected pay;
- `OVERPAID` — confirmed auditable pay is above expected pay;
- `REQUIRES_REVIEW` — evidence or rule allocation is not reliable enough for an automated conclusion; and
- `ACTUAL_PAY_UNAVAILABLE` — expected entitlements were calculated but usable payroll earnings were not supplied.

See [Understanding AuditHero results](docs/UNDERSTANDING_RESULTS.md).

## Documentation

Start at [Documentation home](docs/README.md). The main guides are:

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

## For administrators

The effective-dated Award rule library is stored under `rules/MA000100/`. Fabric and Databricks use the same `schads_audit` Python package and the same rule packs so payroll calculation logic is not maintained separately by platform.

The installer notebooks are the primary UI setup/upgrade path. CLI scripts, REST deployment tooling and CI/CD remain available as optional automation methods.