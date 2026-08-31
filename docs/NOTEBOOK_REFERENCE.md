# AuditHero notebook reference

AuditHero notebooks are the platform-facing orchestration layer. The reusable payroll calculation logic lives in the shared `schads_audit` Python package so Microsoft Fabric and Databricks do not maintain separate SCHADS formulas.

Every operator/admin notebook contains plain-language Markdown/comments before its major code sections. This reference explains what each notebook is for and what the main code blocks are doing.

## Databricks notebooks

| Notebook | What it does |
|---|---|
| `00_setup.py` | Creates/updates Unity Catalog schemas, output/reference tables and views. Run during installation or upgrade. |
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
| `_common.py` | Small shared bootstrap used by the Databricks notebooks to locate the repository/package consistently. |

## Fabric notebooks

| Notebook | What it does |
|---|---|
| `00_setup.py` | Creates Lakehouse schemas/tables, loads rule references and prepares stable BI-facing structures. |
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

### 1. A Markdown introduction

The first cell explains:

- when to run the notebook;
- what it does;
- what it does **not** do; and
- what the operator should run next.

This is intended to make the notebook understandable when opened directly in Fabric or Databricks.

### 2. Parameters/widgets

Databricks notebooks use `dbutils.widgets...` and Fabric notebooks use pipeline/deployer parameter cells.

These blocks expose values such as:

- source/input folder;
- mapping workbook path;
- audit start/end date;
- catalog; or
- optional API configuration.

Changing a parameter changes the input/run scope; it does not change SCHADS formulas.

### 3. Imports from `schads_audit`

Code such as:

```python
from schads_audit.source_mapping import convert_source_files
```

means the notebook is calling a reusable, tested function from the shared package. The notebook deliberately does not copy the implementation of that function into every platform notebook.

Similarly:

```python
from schads_audit.manual_audit import run_manual_audit
```

hands the prepared canonical input data to the shared file-based audit orchestration.

### 4. Input checks before calculation

Notebook blocks that call functions such as `assess_file_readiness(...)` or validate a mapping path are there to stop a run early when the evidence is incomplete or incorrectly mapped.

For example, the conversion notebook refuses to continue to payroll auditing if required canonical fields are still blank after conversion.

### 5. One controlled operation

Each notebook is intended to perform one understandable operation:

- **Setup** → create/update platform structures;
- **Self Test** → validate installation/calculation examples;
- **Mapping Draft** → inspect source schemas and suggest mappings;
- **Convert Source Files** → transform raw exports to canonical datasets;
- **Readiness** → report blocking evidence/data issues;
- **Audit** → execute the entitlement/reconciliation engine; or
- **Build BI** → publish successful results to the reporting layer.

### 6. Platform writes

Functions such as `write_df(...)` convert pandas results to platform Delta tables. These are storage operations; they do not recalculate Award entitlements.

The Fabric audit path also calls the BI snapshot publisher after a successful audit so the Direct Lake report is not replaced by a failed/partial run.

### 7. Display and next action

The last cells normally display a compact table or status summary and print the next recommended operator action.

## Source-mapping notebook flow

The most important new operator notebooks work together as follows:

```text
02d / 03c  Build Source Mapping Workbook
      ↓
operator edits source_mapping.xlsx
      ↓
02e / 03d  Convert Source Files
      ↓
File Readiness
      ↓
03b / 04b  Audit Uploaded Files
```

The platform combined job/pipeline **AuditHero - Convert Mapped Files and Run Audit** chains the conversion, audit and dashboard refresh after the mapping has already been approved.

## Why the Award calculation code is not repeated in notebooks

If every notebook reimplemented overtime, sleepover, public-holiday or minimum-engagement formulas, Fabric and Databricks could drift. AuditHero therefore keeps notebooks readable and platform-focused while routing substantive payroll calculations through the same shared package and effective-dated rule packs.

If you need to understand a specific Award calculation after following the notebook evidence, see [SCHADS rules and evidence](SCHADS_RULES_AND_EVIDENCE.md) and the `calculation_evidence` produced by the audit.
