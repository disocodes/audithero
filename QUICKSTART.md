# AuditHero quick start

This guide takes a payroll/audit operator from an installed AuditHero workspace to a first audit. You do **not** need Employment Hero credentials and you do **not** need to use a terminal.

## 1. Open AuditHero in your platform

- **Microsoft Fabric:** open the AuditHero workspace and `AuditHero_Lakehouse`.
- **Databricks:** open the AuditHero workspace, then **Jobs & Pipelines** and **Catalog Explorer**.

If AuditHero is not installed yet, use the UI-first installation guide for your platform:

- [Microsoft Fabric installation](docs/INSTALL_FABRIC_UI.md)
- [Databricks installation](docs/INSTALL_DATABRICKS_UI.md)

## 2. Upload the exports you already have

If your payroll/HR/timekeeping files use their own headings, upload them unchanged.

**Fabric raw import folder**

`AuditHero_Lakehouse / Files / import / raw`

**Databricks raw import folder**

`/Volumes/schads_payroll/bronze/landing/import/raw`

You can mix CSV and Excel files. Excel workbooks can contain multiple sheets.

If you already have `audithero_input.xlsx` or canonical AuditHero CSV files, upload them directly to the standard input folder and skip to step 6.

## 3. Let AuditHero propose the field mapping

From the platform UI run:

**AuditHero - Build Source Mapping Workbook**

AuditHero inspects file names, Excel sheet names and column headings and creates `source_mapping_draft.xlsx`.

This step does not calculate payroll. It only helps identify where each AuditHero field probably exists in your exports.

## 4. Review and approve the mapping in Excel

Open `source_mapping_draft.xlsx` and review the `field_mapping` sheet.

Each row answers:

> Which field in my export should populate this AuditHero field?

Example:

| AuditHero dataset | AuditHero field | Source field |
|---|---|---|
| employees | employee_id | Employee Number |
| employees | employee_name | Full Name |
| timesheets | start_datetime | Clock In |
| timesheets | end_datetime | Clock Out |
| payroll_earnings | amount | Gross Amount |

Use the `value_mapping` sheet where source values also need translation, for example:

`Permanent FT` → `FULL_TIME`

Save the reviewed workbook as **`source_mapping.xlsx`** in the import folder.

See [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md) for examples covering first/last-name joins, separate date/time fields, defaults, constants and value translations.

## 5. Convert and run the audit

For the normal recurring workflow run:

**AuditHero - Convert Mapped Files and Run Audit**

Enter the required audit start and end dates in the UI and start the job/pipeline.

The workflow automatically:

1. reads your approved `source_mapping.xlsx`;
2. converts the raw exports into AuditHero canonical datasets;
3. writes canonical CSV files and `audithero_input.xlsx`;
4. runs File Readiness checks;
5. stops if required evidence/fields are still missing;
6. runs the SCHADS audit when readiness succeeds; and
7. refreshes the dashboard/report after a successful audit.

If you only want to inspect conversion results before auditing, run **AuditHero - Convert Source Files** instead.

## 6. If your files are already canonical

If the files already use the AuditHero standard format, run:

- **Fabric:** `AuditHero - Uploaded Files Audit Pipeline`
- **Databricks:** `AuditHero - Audit Uploaded CSV Excel`

No mapping step is needed.

## 7. Start with one known payroll period

Do not begin with a multi-year remediation run. Choose one completed period that payroll staff can independently check.

Review:

- expected pay;
- actual auditable pay;
- under/over-payment variance;
- `REQUIRES_REVIEW` items;
- employee and shift evidence; and
- supplemental/TOIL findings where applicable.

Read [Understanding results](docs/UNDERSTANDING_RESULTS.md) before treating any amount as remediation-ready.

## 8. Validate representative cases

Manually calculate representative employees/shifts that cover the conditions actually used by your organisation, for example:

- casual Saturday/Sunday;
- public holiday;
- overtime;
- broken shift;
- sleepover; and
- part-time agreed patterns.

Only expand to the full historical date range after the known period behaves as expected.

## 9. Optional API automation

Employment Hero API connectivity is optional. Add it later if you want direct extraction and scheduled automation.

- Fabric uses Azure Key Vault for API secrets.
- Databricks uses Databricks Secrets.

See [Administration](docs/ADMINISTRATION.md).
