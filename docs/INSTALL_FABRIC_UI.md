# Install AuditHero in Microsoft Fabric

AuditHero can be installed from the **Microsoft Fabric user interface** with a single installer notebook. You do not need to create the Lakehouse, Environment, pipelines, semantic model or report manually.

## What the installer creates

The installer creates or updates the AuditHero application in the current Fabric workspace, including:

- `AuditHero_Lakehouse` with schemas enabled;
- `AuditHero_Environment` with the AuditHero package and required libraries;
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

## Install AuditHero

### 1. Download the installer notebook

From the AuditHero repository, download:

`installers/Fabric_Install_AuditHero.py`

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
5. installs the AuditHero notebooks;
6. creates the Data Factory pipelines;
7. creates the monthly schedule in the configured disabled/enabled state;
8. runs AuditHero Setup;
9. runs AuditHero Self Test; and
10. creates or refreshes the Direct Lake model and Power BI report.

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

Open the installer notebook, change `release_ref` to the approved version if required, and choose **Run all** again.

The installer is designed to update existing AuditHero items rather than require a separate manual upgrade process. After an upgrade, run a known payroll period before relying on the new version for production decisions.

## Uninstall AuditHero

Download and import:

`installers/Fabric_Uninstall_AuditHero.py`

Run the notebook to remove AuditHero-managed pipelines, reporting objects, notebooks and Environment.

The Lakehouse and payroll/audit data are preserved by default.

To permanently remove the AuditHero Lakehouse and all data, the uninstaller requires both:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

This extra confirmation is intentional because Lakehouse deletion removes payroll source files, audit evidence and tables.

## Optional Employment Hero API

If API automation is enabled later, configure Azure Key Vault and the required Employment Hero secrets. Uploaded-file workflows continue to work without API credentials.

See [Administration](ADMINISTRATION.md) for permissions, schedules, source mappings and API configuration.