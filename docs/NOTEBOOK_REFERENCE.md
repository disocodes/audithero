# AuditHero notebook reference

AuditHero notebooks are the platform-facing user and administration layer. The reusable payroll calculation logic lives in the shared `schads_audit` Python package so Microsoft Fabric and Databricks use the same SCHADS formulas and effective-dated rule packs.

Every operator and administration notebook includes plain-language explanations before its major code sections. This reference explains when each notebook is used and what its main sections do.

## Installation and administration notebooks

### First-install bootstrap notebooks

These are imported only when AuditHero is first installed, or when it is being reinstalled after removal.

| Notebook | Platform | What it does |
|---|---|---|
| `installers/Fabric_Install_AuditHero.py` | Microsoft Fabric | Detects the current Fabric workspace, downloads the selected release, creates/updates the AuditHero application, runs Setup/Self Test and builds the reporting layer. |
| `installers/Databricks_Install_AuditHero.py` | Databricks | Uses the current notebook session to install AuditHero workspace files, create/update Jobs and AI/BI resources, then run Setup/Self Test. |

After successful installation, each bootstrap installs permanent administration notebooks inside the platform.

### Installed administration notebooks

**Microsoft Fabric**

- **AuditHero - Install or Upgrade** — reruns the installer against the current workspace and selected `release_ref`.
- **AuditHero - Uninstall** — removes AuditHero application resources while preserving the Lakehouse/data unless full deletion is explicitly confirmed.

**Databricks**

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade` — updates the installed application and reruns Setup/Self Test.
- `/Shared/AuditHero/admin/AuditHero - Uninstall` — removes AuditHero Jobs/dashboard/code and installer-created resources while preserving the catalog/data unless full deletion is explicitly confirmed.

Normal upgrades and removal should use these installed administration notebooks. Command-line deployment remains an optional administrator automation method.

## Databricks notebooks

| Notebook | What it does |
|---|---|
| `00_setup.py` | Creates/updates Unity Catalog schemas, output/reference tables and views. The installer runs this automatically. |
| `01_validate_rules.py` | Loads the effective-dated SCHADS rule manifest and checks that referenced rule packs are usable. |
| `01b_self_test.py` | Runs representative calculations inside the installed Databricks runtime to verify the package/rule deployment. |
| `02_test_employment_hero.py` | Optional API connectivity test. It does not calculate payroll. |
| `02b_audit_readiness.py` | Optional API-mode readiness scan for classifications, pay categories, locations and controlled evidence. |
| `02c_file_readiness.py` | Checks canonical uploaded files and evidence before an audit. |
| `02d_source_mapping_draft.py` | Scans arbitrary CSV/Excel exports and creates an editable source-mapping workbook. |
| `02e_convert_source_files.py` | Applies the approved mapping, writes canonical files and runs File Readiness. |
| `03_historical_audit.py` | Optional Employment Hero API historical audit. |
| `03b_manual_file_audit.py` | Main file-based audit notebook. Reads canonical inputs and writes audit outputs. |
| `04_monthly_payroll_audit.py` | Optional scheduled API-based rolling/monthly audit. |
| `05_rule_analytics.py` | Displays installed effective-dated rule coverage/reference information. |
| `_common.py` | Shared bootstrap used by Databricks notebooks to locate the installed AuditHero package consistently. |

## Microsoft Fabric notebooks

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
| `06_build_bi.py` | Creates/updates BI-facing snapshots, Direct Lake semantic model and Power BI report. |

## How to read an AuditHero notebook

Most AuditHero notebooks follow the same structure.

### 1. Purpose and next action

The opening section explains when to run the notebook, what it changes, what it does not change and what the user should do next.

### 2. Settings and parameters

Installer notebooks expose a small group of installation settings such as `release_ref`, catalog/Lakehouse names and optional API settings. Audit notebooks expose run settings such as source folders and audit dates.

Changing a path or date changes the run scope. It does not change SCHADS calculation formulas.

### 3. Shared AuditHero functions

Code such as:

```python
from schads_audit.source_mapping import convert_source_files
```

uses the shared source-conversion function.

Code such as:

```python
from schads_audit.manual_audit import run_manual_audit
```

runs the shared file-based audit orchestration against prepared canonical inputs.

The notebook explains the purpose of these calls before executing them; the Award formulas are not duplicated in the notebook.

### 4. Validation before calculation

Readiness calls stop the workflow when required fields or evidence are incomplete. This prevents the audit from silently guessing missing data merely because the notebook itself can execute.

### 5. One controlled operation

The main notebook types perform these operations:

- **Install/Upgrade** — create or update the complete platform application;
- **Uninstall** — remove application resources, preserving data unless full deletion is confirmed;
- **Setup** — create/update platform data structures;
- **Self Test** — run representative installation/calculation checks;
- **Mapping Draft** — inspect source schemas and suggest field matches;
- **Convert Source Files** — transform raw exports to canonical datasets;
- **Readiness** — report blocking evidence/data issues;
- **Audit** — execute entitlement and pay reconciliation; and
- **Build BI** — publish successful results to the reporting layer.

### 6. Writes and reporting

Storage helper functions write normalized evidence and calculated outputs into the platform tables. Reporting only uses the latest successful audit result; a failed or partial rerun should not replace the last successful user-facing result.

### 7. Status and next step

The final section normally displays completion status, important findings and the next operator action.

## Source-mapping workflow

```text
Build Source Mapping Workbook
      ↓
review source_mapping.xlsx
      ↓
Convert Source Files
      ↓
File Readiness
      ↓
Audit Uploaded Files
```

The combined **AuditHero - Convert Mapped Files and Run Audit** job/pipeline performs conversion, readiness, audit and report refresh after the mapping has been approved.

## Calculation evidence

For the Award/rule basis of calculated results, see [SCHADS rules and evidence](SCHADS_RULES_AND_EVIDENCE.md) and the `calculation_evidence` fields written by the audit.