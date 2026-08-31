# Install AuditHero in Databricks

AuditHero can be installed from the **Databricks workspace UI** with a single installer notebook. You do not need to create the Unity Catalog objects, jobs or AI/BI dashboard manually.

## What the installer creates

The installer creates or updates:

- the AuditHero workspace folder under `/Shared/AuditHero`;
- the AuditHero Python source, rule packs and configuration templates;
- all AuditHero Databricks notebooks;
- the AuditHero Lakeflow Jobs;
- the AuditHero AI/BI dashboard;
- the `schads_payroll` Unity Catalog structures and landing Volume through Setup; and
- the installation state used by the uninstaller.

It then runs **AuditHero - Setup** and **AuditHero - Self Test** automatically.

Employment Hero credentials are **not** required for installation or uploaded-file audits.

## Before you begin

You need:

- a Databricks workspace with Unity Catalog;
- permission to run a notebook;
- permission to create the AuditHero catalog or permission to use the catalog name you configure;
- permission to create Jobs; and
- access to a SQL warehouse for AI/BI.

The installer can normally select an existing SQL warehouse automatically. If none exists and your permissions allow warehouse creation, it attempts to create a small serverless `AuditHero SQL Warehouse`.

## Install AuditHero

### 1. Import the installer notebook

In Databricks:

1. open **Workspace**;
2. choose **Import**;
3. choose **URL**;
4. use the raw GitHub URL for `installers/Databricks_Install_AuditHero.py` from the approved AuditHero release;
5. open the imported notebook.

Databricks supports importing public notebooks directly from a URL.

### 2. Review the installation settings

For a normal installation, the defaults can remain unchanged:

```python
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
existing_cluster_id = ""
```

Leave `sql_warehouse_id` blank to let AuditHero choose an existing warehouse automatically.

Leave `existing_cluster_id` blank to use Databricks serverless jobs. If serverless jobs are not available in the workspace, enter the ID of an existing compatible cluster and rerun the installer.

### 3. Choose Run all

The installer then:

1. authenticates using the current Databricks notebook session;
2. downloads the selected AuditHero release;
3. installs the AuditHero workspace files and notebooks under `/Shared/AuditHero`;
4. selects or creates the SQL warehouse used by AI/BI;
5. creates or updates the AuditHero dashboard;
6. creates or updates all AuditHero Jobs;
7. runs AuditHero Setup;
8. runs AuditHero Self Test; and
9. saves an installation record for safe removal later.

Do not use production payroll data if Setup or Self Test fails.

## After installation

Normal users work from **Jobs & Pipelines**, **Catalog Explorer** and **AI/BI**.

For organisation-specific CSV/Excel exports:

1. upload the original exports to `/Volumes/schads_payroll/bronze/landing/import/raw`;
2. run **AuditHero - Build Source Mapping Workbook**;
3. review and upload the approved `source_mapping.xlsx`;
4. run **AuditHero - Convert Mapped Files and Run Audit**; and
5. review **AuditHero - SCHADS Payroll Compliance** in AI/BI.

If files already use AuditHero canonical columns, run **AuditHero - Audit Uploaded CSV Excel** directly.

## Upgrade AuditHero

Open the installer notebook, change `release_ref` if required, and choose **Run all** again.

The installer updates the installed notebooks, jobs and dashboard and reruns Setup and Self Test. Validate one known payroll period before relying on the upgraded version in production.

## Uninstall AuditHero

Import the raw GitHub URL for:

`installers/Databricks_Uninstall_AuditHero.py`

Then choose **Run all**.

The uninstaller removes:

- AuditHero Jobs;
- the AuditHero AI/BI dashboard;
- the `/Shared/AuditHero` workspace folder; and
- the SQL warehouse only when the installer created that warehouse.

The AuditHero catalog and payroll/audit data are preserved by default.

To permanently remove the AuditHero catalog and all data, the uninstaller requires:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

This safeguard prevents an ordinary application uninstall from deleting payroll evidence accidentally.

## Optional Employment Hero API

If direct API extraction is enabled later, configure Databricks Secrets and run the optional API connection/readiness jobs. Uploaded-file auditing remains independent of API credentials.

The optional command-line deployment method is documented in [CLI and automation](CLI_AND_AUTOMATION.md).