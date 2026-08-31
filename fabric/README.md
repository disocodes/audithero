# AuditHero on Microsoft Fabric

AuditHero is installed and operated from the **Microsoft Fabric UI**.

## Install or upgrade

Download/import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates the AuditHero Lakehouse, Environment, notebooks, pipelines, schedule, Direct Lake model and Power BI report and runs Setup/Self Test automatically.

See [Install AuditHero in Microsoft Fabric](../docs/INSTALL_FABRIC_UI.md).

## Normal operator workflow

In the AuditHero Fabric workspace:

1. upload original exports to `AuditHero_Lakehouse / Files / import / raw`;
2. run **AuditHero - Build Source Mapping Workbook**;
3. review the generated Excel mapping and upload the approved `source_mapping.xlsx`;
4. run **AuditHero - Convert Mapped Files and Run Audit** for the required dates; and
5. review **AuditHero - SCHADS Payroll Compliance** in Power BI.

If you only want to inspect conversion/readiness, run **AuditHero - Convert Source Files**.

If the exports already use AuditHero canonical format, upload them under `Files/input` and run **AuditHero - Uploaded Files Audit Pipeline** directly.

Employment Hero API connectivity is optional.

## Uninstall

Import `installers/Fabric_Uninstall_AuditHero.py` and run it. Application resources are removed while the Lakehouse is preserved by default. Permanent data removal requires the explicit full-delete confirmation in the notebook.

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)