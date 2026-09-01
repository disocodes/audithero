# AuditHero quick start

This guide covers first installation and a first uploaded-file audit. Employment Hero credentials and a local terminal are not required.

## 1. Install AuditHero

### Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates the AuditHero Lakehouse, Environment, operational notebooks, pipelines, Direct Lake semantic model and Power BI report, then runs Setup and Self Test. It also installs **AuditHero - Install or Upgrade** and **AuditHero - Uninstall** for future administration.

### Databricks

In **Workspace → Import → URL**, import the raw GitHub URL for `installers/Databricks_Install_AuditHero.py`, open it and choose **Run all**.

The installer creates or updates the AuditHero workspace files, Jobs, Unity Catalog structures, AI/BI dashboard, semantic metric views and Genie space, then runs Setup and Self Test. Administration notebooks are installed under `/Shared/AuditHero/admin`.

Detailed installation guides:

- [Microsoft Fabric installation](docs/INSTALL_FABRIC_UI.md)
- [Databricks installation](docs/INSTALL_DATABRICKS_UI.md)

## 2. Open the operating surfaces

- **Microsoft Fabric:** open the AuditHero workspace and `AuditHero_Lakehouse`.
- **Databricks:** open **Jobs & Pipelines** and **Catalog Explorer**.

## 3. Upload the source exports

Upload the original payroll, HR, rostering and timekeeping exports without renaming or rearranging their source columns.

**Fabric raw import folder**

`AuditHero_Lakehouse / Files / import / raw`

**Databricks raw import folder**

`/Volumes/schads_payroll/bronze/landing/import/raw`

CSV and Excel files can be used together. Excel workbooks can contain multiple sheets.

If `audithero_input.xlsx` or canonical AuditHero files are already available, place them in the canonical input folder and continue at step 7.

## 4. Build the source mapping workbook

Run:

**AuditHero - Build Source Mapping Workbook**

AuditHero inspects file names, Excel sheet names and column headings and creates `source_mapping_draft.xlsx`.

This step only proposes source-to-canonical mappings; it does not calculate payroll.

## 5. Review and approve the mapping

Open `source_mapping_draft.xlsx` and review the `field_mapping` sheet.

Example:

| AuditHero dataset | AuditHero field | Source field |
|---|---|---|
| employees | employee_id | Employee Number |
| employees | employee_name | Full Name |
| timesheets | start_datetime | Clock In |
| timesheets | end_datetime | Clock Out |
| payroll_earnings | amount | Gross Amount |

Use the `value_mapping` sheet when source values also need translation, for example:

`Permanent FT` → `FULL_TIME`

Save the reviewed workbook as **`source_mapping.xlsx`** in the import folder.

See [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md) for joins, separate date/time fields, defaults, constants and value translations.

## 6. Convert and run the audit

Run:

**AuditHero - Convert Mapped Files and Run Audit**

Enter the required audit start and end dates.

The workflow:

1. reads the approved `source_mapping.xlsx`;
2. converts the raw exports into AuditHero canonical datasets;
3. writes the canonical files and `audithero_input.xlsx`;
4. runs File Readiness;
5. stops if blocking data or evidence issues remain;
6. runs the SCHADS audit when readiness succeeds; and
7. refreshes the reporting layer after a successful audit.

Run **AuditHero - Convert Source Files** when conversion and readiness need to be reviewed without calculating payroll.

## 7. Canonical uploaded-file audit

If the files already use the AuditHero canonical format, run:

- **Fabric:** `AuditHero - Uploaded Files Audit Pipeline`
- **Databricks:** `AuditHero - Audit Uploaded CSV Excel`

No source-mapping step is required.

## 8. Validate one known payroll period

Use one completed period that payroll or compliance staff can independently verify before expanding to a historical range.

Review:

- expected pay;
- actual auditable pay;
- under/over-payment variance;
- `REQUIRES_REVIEW` items;
- employee and shift evidence; and
- supplemental/TOIL findings where applicable.

Read [Understanding results](docs/UNDERSTANDING_RESULTS.md) before using any amount for remediation.

## 9. Validate representative conditions

Independently check representative employees/shifts covering conditions used by the organisation, for example:

- casual Saturday/Sunday;
- public holiday;
- overtime;
- broken shift;
- sleepover; and
- part-time agreed patterns.

Expand to a historical date range after the known period and representative cases are validated.

## 10. Optional Employment Hero API

Employment Hero API connectivity can be enabled for direct extraction and scheduled audits.

- Fabric stores API secrets in Azure Key Vault.
- Databricks stores API secrets in Databricks Secrets.

See [Administration](docs/ADMINISTRATION.md).

## Upgrade or remove AuditHero

Use the administration notebooks installed by the first installation.

**Fabric**

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

**Databricks**

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

A standard uninstall preserves payroll and audit data. Permanent data removal requires the explicit `DELETE AUDITHERO DATA` confirmation.
