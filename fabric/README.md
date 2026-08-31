# AuditHero on Microsoft Fabric

AuditHero is intended to be operated from the **Fabric UI** after installation.

## Normal operator workflow

In the AuditHero Fabric workspace:

1. upload original exports to `AuditHero_Lakehouse / Files / import / raw`;
2. run **AuditHero - Build Source Mapping Workbook**;
3. review the generated Excel mapping and upload the approved `source_mapping.xlsx`;
4. run **AuditHero - Convert Mapped Files and Run Audit** for the required dates; and
5. review **AuditHero - SCHADS Payroll Compliance** in Power BI.

The combined pipeline converts the mapped source exports to AuditHero canonical datasets, runs readiness checks, executes the SCHADS audit and refreshes the reporting layer after success.

If you only want to inspect conversion/readiness, run **AuditHero - Convert Source Files**.

If the exports are already in AuditHero canonical format, upload them under `Files/input` and run **AuditHero - Uploaded Files Audit Pipeline** directly.

Employment Hero API connectivity is optional.

## Install / upgrade

Use the UI-first guide: [Install AuditHero in Microsoft Fabric](../docs/INSTALL_FABRIC_UI.md).

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)
