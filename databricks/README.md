# AuditHero on Databricks

AuditHero is intended to be operated from the **Databricks UI** after installation.

## Normal operator workflow

Open **Jobs & Pipelines** and use:

1. **AuditHero - Build Source Mapping Workbook** — inspect arbitrary CSV/Excel exports and create an editable field-mapping workbook.
2. Review/download the draft, correct the source-to-AuditHero matches, then upload it as `source_mapping.xlsx`.
3. **AuditHero - Convert Mapped Files and Run Audit** — convert the exports, run File Readiness, execute the selected audit period and refresh AI/BI.
4. Open **AuditHero Payroll Compliance** in AI/BI to review results.

If you only want to validate the mapping/conversion, use **AuditHero - Convert Source Files**.

If the source files already use AuditHero canonical columns, upload them to the canonical input folder and run **AuditHero - Audit Uploaded CSV Excel** directly.

Use **Catalog Explorer** to upload/download files. Standard folders are:

- raw exports: `/Volumes/schads_payroll/bronze/landing/import/raw`
- canonical input: `/Volumes/schads_payroll/bronze/landing/input`

Employment Hero API jobs are optional and clearly labelled `(Optional API)`.

## Install / upgrade

Use the UI-first bundle guide: [Install AuditHero in Databricks](../docs/INSTALL_DATABRICKS_UI.md).

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)
