# AuditHero quick start

Use this guide for a first installation and a first CSV/Excel audit. Employment Hero credentials are optional.

## 1. Install AuditHero

### Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

### Databricks

Import `installers/Databricks_Install_AuditHero.py` into the target Databricks workspace and choose **Run all**.

The installer prepares the required storage, tables, jobs, reporting assets and administration notebooks, then runs Setup and Self Test.

Detailed installation guides:

- [Microsoft Fabric installation](docs/INSTALL_FABRIC_UI.md)
- [Databricks installation](docs/INSTALL_DATABRICKS_UI.md)

Do not use production payroll data until installation and Self Test complete successfully.

## 2. Export the source data

Export the payroll, HR, rostering and timekeeping files required for the audit. Keep the original source column names and file structure.

CSV and Excel files can be used together. Excel workbooks may contain multiple sheets.

## 3. Upload the source files

### Microsoft Fabric

Upload source files to:

`AuditHero_Lakehouse / Files / import / raw`

### Databricks

Upload source files to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

If the files already use the AuditHero canonical format, skip the source-mapping steps and use the canonical uploaded-file audit.

## 4. Build a source mapping

For a new export layout, run:

**AuditHero - Build Source Mapping Workbook**

AuditHero inspects the uploaded files and creates `source_mapping_draft.xlsx`.

The draft proposes how source fields should map to AuditHero fields. It does not calculate payroll.

## 5. Approve the mapping

Open `source_mapping_draft.xlsx` and review the `field_mapping` and `value_mapping` sheets.

Example field mappings:

| AuditHero dataset | AuditHero field | Source field |
|---|---|---|
| employees | employee_id | Employee Number |
| employees | employee_name | Full Name |
| timesheets | start_datetime | Clock In |
| timesheets | end_datetime | Clock Out |
| payroll_earnings | amount | Gross Amount |

Example value mapping:

`Permanent FT` → `FULL_TIME`

Save the approved workbook as **`source_mapping.xlsx`** in the import folder.

See [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md) for joins, defaults, constants, separate date/time fields and value translations.

## 6. Run the audit

Run:

**AuditHero - Convert Mapped Files and Run Audit**

Enter the required audit start and end dates.

The workflow:

1. reads `source_mapping.xlsx`;
2. converts the source files to AuditHero canonical datasets;
3. runs File Readiness;
4. stops if blocking data or evidence issues remain;
5. calculates expected SCHADS entitlements;
6. reconciles expected pay with actual auditable payroll where available;
7. stores audit evidence and results; and
8. refreshes the reporting layer.

Use **AuditHero - Convert Source Files** when conversion and readiness need to be checked before running payroll calculations.

## 7. Review results

### Microsoft Fabric

Review the AuditHero Power BI report.

### Databricks

Review:

- **AuditHero - SCHADS Payroll Compliance** in AI/BI; and
- **AuditHero - Payroll Compliance** in Genie for governed natural-language analysis.

Typical statuses are:

- `COMPLIANT`
- `UNDERPAID`
- `OVERPAID`
- `REQUIRES_REVIEW`
- `ACTUAL_PAY_UNAVAILABLE`

A `REQUIRES_REVIEW` result is not a confirmed underpayment.

See [Understanding results](docs/UNDERSTANDING_RESULTS.md).

## 8. Validate before broader use

Before running a large historical audit, validate one completed payroll period that can be independently checked.

Review representative cases such as:

- Saturday and Sunday penalties;
- public holidays;
- overtime;
- broken shifts;
- sleepovers;
- part-time agreed patterns; and
- allowances or TOIL where applicable.

## 9. Repeat the monthly process

After the source layout has an approved mapping, the routine file workflow is:

1. export the latest source files;
2. upload them to the raw import folder;
3. run **AuditHero - Convert Mapped Files and Run Audit**;
4. enter the audit dates; and
5. review the dashboard, Genie and detailed evidence.

The approved source mapping is reused unless the source-system layout changes.

## 10. Optional Employment Hero API

Employment Hero API connectivity can be configured for direct extraction and recurring monthly or historical audits.

- Fabric stores API secrets in Azure Key Vault.
- Databricks stores API secrets in Databricks Secrets.

See [Administration](docs/ADMINISTRATION.md).

## Upgrade or uninstall

### Microsoft Fabric

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

### Databricks

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

A standard uninstall preserves payroll and audit data. Permanent data removal requires the explicit `DELETE AUDITHERO DATA` confirmation.
