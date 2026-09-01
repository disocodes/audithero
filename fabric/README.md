# AuditHero on Microsoft Fabric

AuditHero is installed, upgraded and operated from the Microsoft Fabric workspace.

## First installation

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates:

- `AuditHero_Lakehouse`;
- `AuditHero_Environment`;
- AuditHero operational notebooks;
- Data Factory pipelines;
- the configured monthly schedule;
- the Direct Lake semantic model; and
- the **AuditHero - SCHADS Payroll Compliance** Power BI report.

Setup and Self Test run during installation. The following administration notebooks are also installed:

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

Later upgrades and removal use the installed administration notebooks.

See [Install AuditHero in Microsoft Fabric](../docs/INSTALL_FABRIC_UI.md).

## CSV / Excel audit workflow

1. Upload original exports to `AuditHero_Lakehouse / Files / import / raw`.
2. For a new or changed source layout, run **AuditHero - Build Source Mapping Workbook**.
3. Review the generated mapping workbook and upload the approved file as `source_mapping.xlsx`.
4. Run **AuditHero - Convert Mapped Files and Run Audit** for the required audit dates.
5. Review **AuditHero - SCHADS Payroll Compliance** in Power BI.

Run **AuditHero - Convert Source Files** when conversion and File Readiness need to be checked without running the payroll audit.

If the source data already uses the AuditHero canonical format, upload it under `Files/input` and run **AuditHero - Uploaded Files Audit Pipeline** directly.

Employment Hero API connectivity is optional.

## Upgrade

Open **AuditHero - Install or Upgrade**, select the approved `release_ref` when required and choose **Run all**. The notebook updates the AuditHero application and reruns the installation validation sequence.

Validate a representative payroll period after an upgrade before resuming recurring production audits.

## Uninstall

Open **AuditHero - Uninstall** and choose **Run all**.

A standard uninstall removes AuditHero application resources while preserving `AuditHero_Lakehouse` and its payroll/audit data. Permanent data removal requires the explicit confirmation phrase `DELETE AUDITHERO DATA` in the uninstaller notebook.

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Install, upgrade and remove](../docs/INSTALL_FABRIC_UI.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [Optional CLI and automation](../docs/CLI_AND_AUTOMATION.md)
