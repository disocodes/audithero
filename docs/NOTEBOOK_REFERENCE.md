# AuditHero notebook reference

AuditHero notebooks provide installation, validation, ingestion, readiness, audit, and reporting operations for Microsoft Fabric and Databricks. Reusable payroll calculation logic is maintained in the shared `schads_audit` Python package so both platforms use the same SCHADS formulas and effective-dated rule packs.

This reference identifies each notebook, its purpose, and when it is used.

## Installation and administration notebooks

### First-install bootstrap notebooks

| Notebook | Platform | Purpose |
|---|---|---|
| `installers/Fabric_Install_AuditHero.py` | Microsoft Fabric | Creates or updates AuditHero workspace resources and runs the installation validation sequence. |
| `installers/Databricks_Install_AuditHero.py` | Databricks | Installs AuditHero workspace files, Jobs, reporting assets, and runs Setup and Self Test. |

After successful installation, managed administration notebooks are available inside each platform.

### Installed administration notebooks

**Microsoft Fabric**

- **AuditHero - Install or Upgrade** — installs an approved AuditHero release into the current workspace or upgrades the existing installation.
- **AuditHero - Uninstall** — removes AuditHero-managed resources while preserving the Lakehouse unless permanent data deletion is explicitly confirmed.

**Databricks**

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade` — installs or upgrades the Databricks deployment and reruns Setup and Self Test.
- `/Shared/AuditHero/admin/AuditHero - Uninstall` — removes AuditHero-managed workspace resources while preserving the catalog unless permanent data deletion is explicitly confirmed.

Command-line deployment is available for automated administration and CI/CD.

## Databricks notebooks

| Notebook | Purpose |
|---|---|
| `00_setup.py` | Creates or updates Unity Catalog schemas, landing folders, rule tables, audit tables, latest-successful views, semantic metric views, and Genie configuration. |
| `00c_setup_genie.py` | Creates or updates the **AuditHero - Payroll Compliance** Genie space after governed data and metric views are available. |
| `00d_verify_dashboard.py` | Verifies the deployed AI/BI dashboard definition and configured SQL warehouse. |
| `01_validate_rules.py` | Validates the effective-dated SCHADS rule manifest and referenced rate, condition, and allowance packs. |
| `01b_self_test.py` | Runs synthetic representative calculations to verify the installed runtime and rule library. |
| `02_test_employment_hero.py` | Tests Employment Hero API authentication and read access. It does not calculate payroll. |
| `02b_audit_readiness.py` | Checks API-source classifications, mappings, locations, and controlled evidence before API-sourced audits. |
| `02c_file_readiness.py` | Checks canonical uploaded files and evidence before a file-based audit. |
| `02d_source_mapping_draft.py` | Scans organisation-specific CSV/XLSX exports and creates `source_mapping_draft.xlsx`. |
| `02e_convert_source_files.py` | Applies an approved source mapping, writes canonical files, and runs File Readiness without starting payroll calculations. |
| `03_historical_audit.py` | Runs an Employment Hero API historical audit for a specified date range. |
| `03b_manual_file_audit.py` | Runs the canonical uploaded-file audit and stores normalized evidence and audit results. |
| `04_monthly_payroll_audit.py` | Runs the recurring Employment Hero API audit over a rolling date window. |
| `05_rule_analytics.py` | Displays the effective-dated base-rate history for a selected canonical classification. |
| `_common.py` | Shared Databricks notebook bootstrap that locates the installed AuditHero source package. |

Routine Databricks operation is performed through **Jobs & Pipelines**, with results reviewed in **AI/BI** and **Genie**.

## Microsoft Fabric notebooks

| Notebook | Purpose |
|---|---|
| `00_setup.py` | Creates Lakehouse schemas and tables, loads rule references, and prepares reporting structures. |
| `01_self_test.py` | Runs synthetic representative calculations inside the installed Fabric Environment. |
| `02_connection_test.py` | Tests Employment Hero API authentication and read access. |
| `03_readiness.py` | Checks API-source mappings and controlled evidence before API-sourced audits. |
| `03b_file_readiness.py` | Checks canonical uploaded files and evidence before a file-based audit. |
| `03c_source_mapping_draft.py` | Scans raw CSV/XLSX exports and creates the editable source-mapping workbook. |
| `03d_convert_source_files.py` | Converts mapped source exports to canonical files and runs File Readiness. |
| `04_historical_audit.py` | Runs an Employment Hero API historical audit. |
| `04b_manual_file_audit.py` | Runs the canonical uploaded-file audit and publishes the successful reporting snapshot. |
| `05_monthly_audit.py` | Runs the recurring Employment Hero API audit. |
| `06_build_bi.py` | Creates or updates the Direct Lake semantic model, AuditHero measures, and Power BI report. |

Routine Fabric operation is performed through the deployed Data Factory pipelines and Power BI report.

## Common notebook structure

AuditHero notebooks use a consistent structure where applicable.

### Purpose

The opening section identifies the operation performed by the notebook and whether it reads or writes payroll data.

### Parameters

Installation notebooks expose deployment settings such as release, catalog or Lakehouse names, and optional API settings. Audit notebooks expose run settings such as source folders and audit dates.

Changing a source path or audit date changes the scope of a run; it does not change the SCHADS calculation rules.

### Validation

Setup, rule validation, Self Test, and readiness checks stop the workflow when required runtime, rule, or evidence conditions are not satisfied.

### Calculation

Audit notebooks call the shared `schads_audit` package for entitlement calculations and reconciliation. Platform notebooks do not maintain separate Award formulas.

### Persistence

Normalized source evidence and calculated outputs are stored in platform tables with audit-run identifiers so reruns remain traceable.

### Reporting

Reporting views and snapshots expose successful audit results. Review statuses remain distinct from definitive underpayment or overpayment results.

## Source-mapping workflow

```text
Build Source Mapping Workbook
      ↓
review and save source_mapping.xlsx
      ↓
Convert Mapped Files and Run Audit
      ↓
File Readiness
      ↓
SCHADS audit
      ↓
reporting refresh
```

Use **AuditHero - Convert Source Files** when conversion and readiness need to be reviewed without running payroll calculations.

## Calculation evidence

For the Award and rule basis of calculated results, see [SCHADS rules and evidence](SCHADS_RULES_AND_EVIDENCE.md) and the `calculation_evidence` fields stored with audit results.
