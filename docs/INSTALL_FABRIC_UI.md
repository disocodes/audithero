# Install AuditHero in Microsoft Fabric

AuditHero can be installed from the **Microsoft Fabric user interface** with one bootstrap notebook. The installer creates the required Lakehouse, Environment, pipelines, semantic model and report.

## What the installer creates

The installer creates or updates the AuditHero application in the current Fabric workspace, including:

- `AuditHero_Lakehouse` with schemas enabled;
- `AuditHero_Environment` with the AuditHero package and required libraries;
- **AuditHero - Install or Upgrade** for future upgrades;
- **AuditHero - Uninstall** for removal;
- Setup and Self Test notebooks;
- CSV/Excel source-mapping and conversion notebooks;
- uploaded-file audit notebooks;
- historical and monthly API notebooks;
- Data Factory pipelines;
- the configured monthly schedule;
- the Direct Lake semantic model; and
- the **AuditHero - SCHADS Payroll Compliance** Power BI report.

Employment Hero credentials are not required for installation or uploaded-file audits.

## Requirements

The Fabric workspace must provide:

- active Fabric capacity;
- permission to create and manage workspace items; and
- permission to run Fabric notebooks.

The installer detects the current workspace ID and workspace name from the notebook session.

## First installation

### 1. Import the bootstrap notebook

Download `installers/Fabric_Install_AuditHero.py` from the approved AuditHero release.

In the target Fabric workspace:

1. choose **Import**;
2. choose **Notebook**;
3. upload `Fabric_Install_AuditHero.py`; and
4. open the imported notebook.

The bootstrap installs managed administration notebooks for later upgrades and removal.

### 2. Review installation settings

The default settings are:

```python
release_ref = "main"
lakehouse_name = "AuditHero_Lakehouse"
environment_name = "AuditHero_Environment"
key_vault_url = ""
monthly_schedule_enabled = False
```

Leave `key_vault_url` blank for uploaded-file audits. Keep `monthly_schedule_enabled = False` until a representative payroll period has been validated.

### 3. Choose Run all

The installer performs the following sequence:

1. detects the current Fabric workspace;
2. downloads the selected AuditHero release;
3. creates or updates the schema-enabled Lakehouse;
4. builds and publishes the AuditHero Environment;
5. installs the operational and administration notebooks;
6. creates or updates the Data Factory pipelines;
7. creates the monthly schedule in the configured state;
8. runs AuditHero Setup;
9. runs AuditHero Self Test; and
10. creates or refreshes the Direct Lake semantic model and Power BI report.

After successful first installation, the imported bootstrap copy can be removed because **AuditHero - Install or Upgrade** is installed in the workspace.

Do not use production payroll data if Setup or Self Test fails.

## CSV / Excel audit workflow

1. Upload source exports to `AuditHero_Lakehouse / Files / import / raw`.
2. For a new or changed source layout, run **AuditHero - Build Source Mapping Workbook**.
3. Review the generated workbook and upload the approved mapping as `source_mapping.xlsx`.
4. Run **AuditHero - Convert Mapped Files and Run Audit** for the required dates.
5. Review **AuditHero - SCHADS Payroll Compliance** in Power BI.

If the source files already use the AuditHero canonical format, place them under `Files/input` and run **AuditHero - Uploaded Files Audit Pipeline**.

Run **AuditHero - Convert Source Files** when conversion and File Readiness need to be checked without calculating payroll.

## Upgrade AuditHero

Open **AuditHero - Install or Upgrade**, set `release_ref` to the approved release when required and choose **Run all**.

The installer refreshes the existing AuditHero application and reruns the installation validation sequence. Validate a known payroll period after an upgrade before resuming recurring production audits.

## Uninstall AuditHero

Open **AuditHero - Uninstall** and choose **Run all**.

A standard uninstall removes AuditHero-managed pipelines, reporting objects, operational notebooks, Environment and administration notebooks while preserving the Lakehouse and payroll/audit data.

To permanently remove the AuditHero Lakehouse and all data, set:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

Permanent deletion removes payroll source files, audit evidence and Lakehouse tables.

## Reinstall against preserved data

If AuditHero was removed without deleting the Lakehouse, import the bootstrap installer again. Installation can recreate the application resources while retaining the preserved AuditHero storage.

## Optional Employment Hero API

To enable API extraction, configure Azure Key Vault and the required Employment Hero secrets. Uploaded-file workflows remain available without API credentials.

See [Administration](ADMINISTRATION.md) for permissions, schedules, source mappings and API configuration.
