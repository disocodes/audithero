# AuditHero on Databricks

AuditHero is installed and operated from the **Databricks UI**.

## Install or upgrade

In **Workspace → Import → URL**, import the public raw URL for `installers/Databricks_Install_AuditHero.py`, open it and choose **Run all**.

The installer creates or updates the AuditHero workspace files/notebooks, jobs and AI/BI dashboard and runs Setup/Self Test automatically.

See [Install AuditHero in Databricks](../docs/INSTALL_DATABRICKS_UI.md).

## Normal operator workflow

Open **Jobs & Pipelines** and use:

1. **AuditHero - Build Source Mapping Workbook** — inspect arbitrary CSV/Excel exports and create an editable field-mapping workbook.
2. Review/download the draft, correct the source-to-AuditHero matches, then upload it as `source_mapping.xlsx`.
3. **AuditHero - Convert Mapped Files and Run Audit** — convert the exports, run File Readiness, execute the selected audit period and refresh AI/BI.
4. Open **AuditHero - SCHADS Payroll Compliance** in AI/BI to review results.

If you only want to validate mapping/conversion, use **AuditHero - Convert Source Files**.

If the source files already use AuditHero canonical columns, upload them to the canonical input folder and run **AuditHero - Audit Uploaded CSV Excel** directly.

Use **Catalog Explorer** to upload/download files. Standard folders are:

- raw exports: `/Volumes/schads_payroll/bronze/landing/import/raw`
- canonical input: `/Volumes/schads_payroll/bronze/landing/input`

Employment Hero API jobs are optional and clearly labelled `(Optional API)`.

## Uninstall

Import the public raw URL for `installers/Databricks_Uninstall_AuditHero.py` and choose **Run all**. AuditHero application resources are removed while the catalog/data are preserved by default. Permanent data removal requires the explicit full-delete confirmation in the notebook.

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)