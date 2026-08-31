# Install AuditHero in Microsoft Fabric

AuditHero can be installed from the **Microsoft Fabric user interface** with a single bootstrap notebook. You do not need to create the Lakehouse, Environment, pipelines, semantic model or report manually.

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
- a disabled-by-default monthly schedule;
- the Direct Lake semantic model; and
- the AuditHero Power BI report.

Employment Hero credentials are **not** required for installation or uploaded-file audits.

## Before you begin

You need:

- a Microsoft Fabric workspace on active capacity;
- permission in that workspace to create and manage Fabric items; and
- permission to run a Fabric notebook.

The installer detects the current workspace ID and workspace name automatically.

## First installation

### 1. Download the bootstrap notebook

From the AuditHero repository, download:

`installers/Fabric_Install_AuditHero.py`

You need this external bootstrap only for the first installation. AuditHero installs its own managed Install/Upgrade notebook into the workspace for future use.

### 2. Import it into Fabric

In the target Fabric workspace:

1. choose **Import**;
2. choose **Notebook**;
3. upload `Fabric_Install_AuditHero.py`;
4. open the imported notebook.

### 3. Review the installation settings

At the top of the notebook you can change the release or item names if required. For a normal installation, the defaults can remain unchanged.

The main settings are:

- `release_ref = "main"`
- `lakehouse_name = "AuditHero_Lakehouse"`
- `environment_name = "AuditHero_Environment"`
- `key_vault_url = ""`
- `monthly_schedule_enabled = False`

Leave `key_vault_url` blank when you are using CSV/Excel uploads only.

### 4. Choose Run all

The notebook then:

1. detects the current Fabric workspace;
2. downloads the selected AuditHero release;
3. creates or updates the schema-enabled Lakehouse;
4. builds and publishes the AuditHero Fabric Environment;
5. installs the AuditHero operational notebooks;
6. installs **AuditHero - Install or Upgrade** and **AuditHero - Uninstall**;
7. creates the Data Factory pipelines;
8. creates the monthly schedule in the configured disabled/enabled state;
9. runs AuditHero Setup;
10. runs AuditHero Self Test; and
11. creates or refreshes the Direct Lake model and Power BI report.

After a successful first installation, the temporary bootstrap notebook attempts to remove itself because the managed administration notebooks are already installed.

Do not use production payroll data if the installer reports that Setup or Self Test failed.

## After installation

Normal payroll users work from the Fabric UI. The usual file-based workflow is:

1. upload source exports to `AuditHero_Lakehouse / Files / import / raw`;
2. run **AuditHero - Build Source Mapping Workbook**;
3. review the generated mapping workbook and upload the approved `source_mapping.xlsx`;
4. run **AuditHero - Convert Mapped Files and Run Audit**; and
5. review **AuditHero - SCHADS Payroll Compliance** in Power BI.

If the source files already use AuditHero canonical columns, run **AuditHero - Uploaded Files Audit Pipeline** instead.

## Upgrade AuditHero

Open **AuditHero - Install or Upgrade** in the Fabric workspace. Change `release_ref` to the approved version if required and choose **Run all**.

The installer updates the existing AuditHero application and reruns Setup and Self Test. Validate one known payroll period before relying on an upgraded version for production decisions.

## Uninstall AuditHero

Open **AuditHero - Uninstall** in the Fabric workspace and choose **Run all**.

A normal uninstall removes AuditHero-managed pipelines, reporting objects, operational notebooks, Environment and administration notebooks. The running uninstaller removes itself as its last application-cleanup step.

The Lakehouse and payroll/audit data are preserved by default.

To permanently remove the AuditHero Lakehouse and all data, set both values before running the uninstaller:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

This extra confirmation prevents an ordinary application uninstall from deleting payroll source files, audit evidence and tables.

## Reinstall against preserved data

If AuditHero was uninstalled without deleting the Lakehouse, import the bootstrap installer again. The installer can recreate the application resources against the preserved AuditHero storage.

## Optional Employment Hero API

If API automation is enabled later, configure Azure Key Vault and the required Employment Hero secrets. Uploaded-file workflows continue to work without API credentials.

See [Administration](ADMINISTRATION.md) for permissions, schedules, source mappings and API configuration.