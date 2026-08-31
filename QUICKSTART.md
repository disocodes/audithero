# AuditHero quick start

This guide gets an operator from an installed AuditHero workspace to a first audit. You do not need Employment Hero credentials and you do not need to use a terminal.

## 1. Open the installed platform

Choose your platform:

- **Microsoft Fabric:** open the AuditHero workspace and its `AuditHero_Lakehouse`.
- **Databricks:** open the AuditHero workspace, then **Jobs & Pipelines** and **Catalog Explorer**.

If AuditHero has not been installed yet, use the UI-first installation guides:

- [Microsoft Fabric installation](docs/INSTALL_FABRIC_UI.md)
- [Databricks installation](docs/INSTALL_DATABRICKS_UI.md)

## 2. Upload your source exports

You have two choices.

### Your files already use AuditHero's standard format

Upload `audithero_input.xlsx` or the canonical CSV files directly to the standard input folder:

- Fabric: `AuditHero_Lakehouse / Files / input`
- Databricks: `/Volumes/schads_payroll/bronze/landing/input`

Then go to step 5.

### Your files use your payroll system's own fields

Upload the original files without manually renaming columns:

- Fabric: `AuditHero_Lakehouse / Files / import / raw`
- Databricks: `/Volumes/schads_payroll/bronze/landing/import/raw`

CSV and Excel files can be mixed.

## 3. Build and edit the source mapping workbook

Run **AuditHero - Build Source Mapping Workbook** from the platform UI.

AuditHero inspects file names, Excel sheet names and column headers and creates `source_mapping_draft.xlsx`.

Open the workbook and review the `field_mapping` sheet. Each row answers a simple question:

> Which source field should populate this AuditHero field?

For example:

| Dataset | AuditHero field | Your source field |
|---|---|---|
| employees | employee_id | Employee Number |
| employees | employee_name | Full Name |
| timesheets | start_datetime | Clock In |
| timesheets | end_datetime | Clock Out |
| payroll_earnings | amount | Gross Amount |

Use `value_mapping` when source values need translation, for example `Permanent FT` → `FULL_TIME`.

Save the approved file as **`source_mapping.xlsx`** in the import folder.

See [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md) for advanced examples such as combining first/last name, separate date/time fields, defaults and constants.

## 4. Convert the source files

Run **AuditHero - Convert Source Files**.

The job/pipeline:

1. reads your approved mapping;
2. converts the source exports to AuditHero's canonical datasets;
3. writes canonical CSV files and `audithero_input.xlsx`;
4. writes `conversion_report.csv`; and
5. runs File Readiness checks.

If the conversion stops, read the blocking rows shown by File Readiness, correct the source data or mapping, and rerun conversion.

## 5. Run one known payroll period first

Do not begin with a multi-year remediation run. Choose one completed period that payroll staff can manually verify.

- Fabric: run **AuditHero - Uploaded Files Audit Pipeline**.
- Databricks: run **AuditHero - Audit Uploaded CSV Excel**.

Set the audit start and end dates in the UI parameters and run the workflow.

## 6. Review the dashboard

Check:

- expected pay;
- actual auditable pay;
- under/over-payment variance;
- `REQUIRES_REVIEW` items;
- employee/shift evidence; and
- supplemental/TOIL findings where applicable.

Read [Understanding results](docs/UNDERSTANDING_RESULTS.md) before treating a number as remediation-ready.

## 7. Validate representative cases

Manually calculate a sample that covers the conditions you use in practice, such as casual Saturday, Sunday/public holiday, overtime, broken shift, sleepover and part-time patterns.

Only after the known period reconciles should you expand to the historical date range.

## 8. Optional API automation

Employment Hero API connectivity is optional. Add it only if you want direct extraction and recurring automation.

- Fabric uses Azure Key Vault for API secrets.
- Databricks uses Databricks Secrets.

See [Administration](docs/ADMINISTRATION.md).
