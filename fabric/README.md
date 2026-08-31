# AuditHero on Microsoft Fabric

AuditHero is installed, upgraded, operated and removed from the **Microsoft Fabric UI**.

## First installation

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates:

- `AuditHero_Lakehouse`;
- `AuditHero_Environment`;
- AuditHero notebooks;
- Data Factory pipelines;
- the monthly schedule in its configured disabled/enabled state;
- the Direct Lake semantic model; and
- the AuditHero Power BI report.

It then runs Setup and Self Test automatically and installs two permanent administration notebooks:

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

After the first installation, use those installed notebooks for upgrades and removal. You do not need to import the bootstrap again unless you are reinstalling after removal.

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

## Upgrade

Open **AuditHero - Install or Upgrade**, select the approved `release_ref` if required and choose **Run all**. The notebook updates the existing AuditHero application and reruns Setup and Self Test.

## Uninstall

Open **AuditHero - Uninstall** and choose **Run all**.

The normal uninstall removes AuditHero application resources while preserving `AuditHero_Lakehouse` and its payroll/audit data. Permanent data removal requires the explicit confirmation phrase `DELETE AUDITHERO DATA` inside the uninstaller notebook.

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Install, upgrade and remove](../docs/INSTALL_FABRIC_UI.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)