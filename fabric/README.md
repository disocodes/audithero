# AuditHero on Microsoft Fabric

AuditHero is intended to be operated from the Fabric UI after installation.

## Normal operator workflow

In the AuditHero Fabric workspace:

1. upload original exports to `AuditHero_Lakehouse / Files / import / raw`;
2. run **AuditHero - Build Source Mapping Workbook**;
3. review/upload the approved `source_mapping.xlsx`;
4. run **AuditHero - Convert Source Files**;
5. run **AuditHero - Uploaded Files Audit Pipeline** for the required dates; and
6. review **AuditHero - SCHADS Payroll Compliance** in Power BI.

If the exports are already in canonical AuditHero format, upload them under `Files/input` and skip the mapping/conversion steps.

Employment Hero API connectivity is optional.

## Install / upgrade

Use the UI-first guide: [Install AuditHero in Microsoft Fabric](../docs/INSTALL_FABRIC_UI.md).

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)
