# AuditHero on Databricks

AuditHero is intended to be operated from the Databricks UI after installation.

## Normal operator workflow

Open **Jobs & Pipelines** and use:

1. **AuditHero - Build Source Mapping Workbook** — inspect arbitrary CSV/Excel exports and produce an editable field-mapping workbook.
2. **AuditHero - Convert Source Files** — apply the approved mapping and create the canonical AuditHero input files.
3. **AuditHero - File Readiness** — validate data/evidence without calculating payroll.
4. **AuditHero - Audit Uploaded CSV Excel** — run the selected audit period.
5. Open **AuditHero Payroll Compliance** in AI/BI to review results.

Use **Catalog Explorer** to upload/download files. The standard folders are:

- raw exports: `/Volumes/schads_payroll/bronze/landing/import/raw`
- canonical input: `/Volumes/schads_payroll/bronze/landing/input`

Employment Hero API jobs are optional and clearly labelled `(Optional API)`.

## Install / upgrade

Use the UI-first bundle guide: [Install AuditHero in Databricks](../docs/INSTALL_DATABRICKS_UI.md).

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)
