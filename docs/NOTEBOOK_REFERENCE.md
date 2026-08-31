# AuditHero notebook reference

AuditHero notebooks are the platform-facing orchestration layer. The reusable payroll calculation logic lives in the shared `schads_audit` Python package so Microsoft Fabric and Databricks do not maintain separate SCHADS formulas.

Every operator/admin notebook contains plain-language Markdown/comments before its major code sections. This reference explains what each notebook is for and what the main code blocks are doing.

## Installation notebooks

These notebooks are intended to be run directly from the platform UI.

| Notebook | Platform | What it does |
|---|---|---|
| `installers/Fabric_Install_AuditHero.py` | Microsoft Fabric | Detects the current workspace, downloads the selected AuditHero release, creates/updates Fabric items, runs Setup/Self Test and builds the BI layer. |
| `installers/Fabric_Uninstall_AuditHero.py` | Microsoft Fabric | Removes AuditHero-managed application items. Lakehouse data is preserved unless the explicit full-delete confirmation is entered. |
| `installers/Databricks_Install_AuditHero.py` | Databricks | Uses notebook authentication to install AuditHero workspace files/notebooks, create/update Jobs and AI/BI, then run Setup/Self Test. |
| `installers/Databricks_Uninstall_AuditHero.py` | Databricks | Removes AuditHero jobs/dashboard/code and any SQL warehouse created by the installer. The catalog is preserved unless full deletion is explicitly confirmed. |

The installer notebooks are the normal first-install and upgrade path. The command-line deployers remain optional administrator automation.

## Databricks notebooks

| Notebook | What it does |
|---|---|
| `00_setup.py` | Creates/updates Unity Catalog schemas, output/reference tables and views. The installer runs this automatically. |
| `01_validate_rules.py` | Loads the effective-dated SCHADS rule manifest and checks that referenced rule packs are valid. |
| `01b_self_test.py` | Runs representative calculations inside the installed Databricks runtime to detect broken rule/package deployments. |
| `02_test_employment_hero.py` | Optional API connectivity test. It does not calculate payroll. |
| `02b_audit_readiness.py` | Optional API-mode readiness scan for classifications, pay categories, locations and controlled evidence. |
| `02c_file_readiness.py` | Checks canonical uploaded files/evidence before an audit. |
| `02d_source_mapping_draft.py` | Scans arbitrary CSV/Excel exports and creates an editable source-mapping workbook. |
| `02e_convert_source_files.py` | Applies the approved mapping, writes canonical files and runs File Readiness. |
| `03_historical_audit.py` | Optional Employment Hero API historical audit. |
| `03b_manual_file_audit.py` | Main file-based audit notebook. Reads canonical inputs and writes audit outputs. |
| `04_monthly_payroll_audit.py` | Optional scheduled API-based rolling/monthly audit. |
| `05_rule_analytics.py` | Displays the installed effective-dated rule coverage/reference information. |
| `_common.py` | Small shared bootstrap used by the Databricks notebooks to locate the installed package consistently. |

## Fabric notebooks

| Notebook | What it does |
|---|---|
| `00_setup.py` | Creates Lakehouse schemas/tables, loads rule references and prepares stable BI-facing structures. The installer runs this automatically. |
| `01_self_test.py` | Runs representative rule calculations inside Fabric. |
| `02_connection_test.py` | Optional Employment Hero API connection test. |
| `03_readiness.py` | Optional API-mode readiness scan. |
| `03b_file_readiness.py` | Checks canonical uploaded data/evidence. |
| `03c_source_mapping_draft.py` | Scans raw exports and creates the editable source-mapping workbook. |
| `03d_convert_source_files.py` | Converts raw exports to canonical files and validates them. |
| `04_historical_audit.py` | Optional API historical audit. |
| `04b_manual_file_audit.py` | Main uploaded-file audit. |
| `05_monthly_audit.py` | Optional scheduled API audit. |
| `06_build_bi.py` | Creates/updates BI-facing snapshot tables, Direct Lake semantic model and Power BI report structures. |

## How the notebooks are organised

Most AuditHero notebooks follow the same pattern.

### 1. A plain-language introduction

The first section explains:

- when to run the notebook;
- what it does;
- what it does **not** do; and
- what the operator should run next.

### 2. Parameters/widgets

Databricks notebooks use job/notebook parameters and Fabric notebooks use parameter cells/pipeline parameters. These expose values such as source folders, mapping workbook path, audit dates, catalog or optional API settings.

Changing these parameters changes the input/run scope; it does not change SCHADS formulas.

### 3. Imports from `schads_audit`

Code such as:

```python
from schads_audit.source_mapping import convert_source_files
```

calls a reusable function from the shared AuditHero package.

Similarly:

```python
from schads_audit.manual_audit import run_manual_audit
```

passes prepared canonical input data to the shared file-based audit orchestration.

### 4. Input checks before calculation

Calls such as `assess_file_readiness(...)` stop the workflow early when the evidence is incomplete or incorrectly mapped. The conversion notebook does not continue to payroll auditing when blocking required fields remain unresolved.

### 5. One controlled operation

Each notebook is intended to perform one understandable operation:

- **Install/Upgrade** → create/update the complete platform application;
- **Uninstall** → remove application resources, preserving data unless full deletion is confirmed;
- **Setup** → create/update platform data structures;
- **Self Test** → validate installation/calculation examples;
- **Mapping Draft** → inspect source schemas and suggest mappings;
- **Convert Source Files** → transform raw exports to canonical datasets;
- **Readiness** → report blocking evidence/data issues;
- **Audit** → execute the entitlement/reconciliation engine; or
- **Build BI** → publish successful results to the reporting layer.

### 6. Platform writes

Functions such as `write_df(...)` convert results to platform Delta tables. These are storage operations; they do not independently recalculate Award entitlements.

The Fabric audit path also publishes the latest successful snapshot so a failed/partial run does not replace the current reporting dataset.

### 7. Display and next action

The last sections normally show a status summary and the next operator action.

## Source-mapping notebook flow

```text
Build Source Mapping Workbook
      ↓
operator reviews source_mapping.xlsx
      ↓
Convert Source Files
      ↓
File Readiness
      ↓
Audit Uploaded Files
```

The platform combined job/pipeline **AuditHero - Convert Mapped Files and Run Audit** chains conversion, audit and dashboard refresh after the mapping has been approved.

## Why the Award calculation code is not repeated in notebooks

Fabric and Databricks both call the same shared package and effective-dated rule packs. This avoids maintaining separate overtime, sleepover, public-holiday or minimum-engagement formulas by platform.

For calculation evidence, see [SCHADS rules and evidence](SCHADS_RULES_AND_EVIDENCE.md) and the `calculation_evidence` fields produced by the audit.