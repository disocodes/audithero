# AuditHero notebook reference

AuditHero notebooks are orchestration/user-interface notebooks. The reusable payroll logic lives in the shared `schads_audit` package so Fabric and Databricks do not maintain different calculation formulas.

The notebook source files also contain inline explanations of their parameters, processing steps and outputs.

## Databricks notebooks

| Notebook | Purpose |
|---|---|
| `00_setup.py` | Creates/updates Unity Catalog schemas, output tables, rule-reference tables and views. Run at installation/upgrade. |
| `01_validate_rules.py` | Validates the effective-dated rule library/manifest. |
| `01b_self_test.py` | Runs representative regression calculations inside Databricks. |
| `02_test_employment_hero.py` | Optional API connectivity check. Does not run a payroll audit. |
| `02b_audit_readiness.py` | Optional API-mode mapping/evidence readiness scan. |
| `02c_file_readiness.py` | Checks canonical uploaded files and evidence before an audit. |
| `02d_source_mapping_draft.py` | Scans arbitrary CSV/Excel exports and creates an editable source mapping workbook. |
| `02e_convert_source_files.py` | Applies the approved mapping, writes canonical files and runs File Readiness. |
| `03_historical_audit.py` | Optional Employment Hero API historical audit. |
| `03b_manual_file_audit.py` | Main uploaded-file historical/date-range audit. |
| `04_monthly_payroll_audit.py` | Optional scheduled API-based rolling/monthly audit. |
| `05_rule_analytics.py` | Displays rule-library coverage/reference information. |

## Fabric notebooks

| Notebook | Purpose |
|---|---|
| `00_setup.py` | Creates Lakehouse schemas/tables, loads rule references and creates stable BI structures. |
| `01_self_test.py` | Runs representative rule calculations inside Fabric. |
| `02_connection_test.py` | Optional Employment Hero API connection check. |
| `03_readiness.py` | Optional API-mode readiness scan. |
| `03b_file_readiness.py` | Checks canonical uploaded data/evidence. |
| `03c_source_mapping_draft.py` | Creates the editable mapping workbook from raw exports. |
| `03d_convert_source_files.py` | Converts raw exports to canonical files and validates them. |
| `04_historical_audit.py` | Optional API historical audit. |
| `04b_manual_file_audit.py` | Main uploaded-file audit. |
| `05_monthly_audit.py` | Optional scheduled API audit. |
| `06_build_bi.py` | Creates/updates BI-facing snapshots/model/report structures. |

## How to read an AuditHero notebook

The notebooks follow a consistent pattern:

1. **Purpose/parameters** — what the notebook does and what the UI parameters mean.
2. **Load shared engine/configuration** — imports the tested reusable package rather than embedding formulas in the notebook.
3. **Validate inputs** — refuses to continue when required evidence/fields are missing.
4. **Run one controlled operation** — setup, mapping, conversion, audit or BI build.
5. **Display operator output** — tables/status summaries and the next action.

## Why calculation code is not repeated in notebooks

If every notebook reimplemented overtime, sleepover or public-holiday formulas, Fabric and Databricks could drift. AuditHero therefore keeps platform notebooks thin enough to be understandable while routing the substantive calculations through the same library and effective-dated rule packs.
