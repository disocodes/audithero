# Install AuditHero in Databricks

AuditHero can be installed from the **Databricks workspace UI** with one bootstrap notebook.

## What the installer creates

The installer creates or updates:

- `/Shared/AuditHero` workspace files and managed notebooks;
- **AuditHero - Install or Upgrade** and **AuditHero - Uninstall**;
- all AuditHero Jobs;
- a SQL warehouse for AI/BI when no suitable warehouse exists and permissions allow creation;
- the published **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard;
- the `schads_payroll` Unity Catalog, schemas and landing Volume;
- the standard raw-import and canonical-input folders;
- effective-dated SCHADS reference tables;
- Silver normalized-evidence tables and Gold audit-result tables;
- governed Unity Catalog metric views under `schads_payroll.semantic`; and
- the **AuditHero - Payroll Compliance** Genie space.

The installer then runs **AuditHero - Setup** and **AuditHero - Self Test**.

Employment Hero credentials are not required for installation or uploaded CSV/Excel audits.

## Requirements

The Databricks workspace must provide:

- Unity Catalog;
- permission to run notebooks and Jobs;
- permission to create or use the configured AuditHero catalog;
- access to a SQL warehouse; and
- Genie if natural-language analysis will be used.

Unity Catalog metric views must be supported by the Databricks runtime/SQL environment used for AuditHero.

## First installation

### 1. Import the bootstrap notebook

In Databricks:

1. open **Workspace**;
2. choose **Import**;
3. choose **URL**;
4. enter the raw GitHub URL for `installers/Databricks_Install_AuditHero.py` from the approved AuditHero release; and
5. open the imported notebook.

### 2. Review the installation settings

Default settings are:

```python
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
existing_cluster_id = ""
```

Leave `sql_warehouse_id` blank to use an available SQL warehouse or create **AuditHero SQL Warehouse** when permitted.

Leave `existing_cluster_id` blank to use serverless Jobs where supported. If serverless Jobs are not available, enter a compatible existing cluster ID.

### 3. Choose Run all

The installer performs the following sequence:

1. authenticates with the current Databricks session;
2. downloads the selected AuditHero release;
3. installs the workspace files and notebooks;
4. selects or creates the SQL warehouse;
5. creates or updates the AI/BI dashboard;
6. creates or updates the AuditHero Jobs;
7. runs **AuditHero - Setup**;
8. Setup creates the catalog, Volume folders, Delta structures, reference rules, Gold views and metric views;
9. Setup creates or updates the AuditHero Genie space;
10. validation and Self Test complete; and
11. installation state is recorded for upgrades and uninstall.

Do not use production payroll data if Setup or Self Test fails.

## Uploaded CSV/Excel workflow

After installation:

1. Export the required payroll, HR, rostering and timekeeping CSV/XLSX files.
2. In **Catalog Explorer**, upload the files to `/Volumes/schads_payroll/bronze/landing/import/raw`.
3. For a new export layout, run **AuditHero - Build Source Mapping Workbook**.
4. Review `source_mapping_draft.xlsx` and save the approved mapping as `/Volumes/schads_payroll/bronze/landing/import/source_mapping.xlsx`.
5. Run **AuditHero - Convert Mapped Files and Run Audit** and enter the audit start and end dates.
6. AuditHero converts the source data, runs File Readiness, stores normalized evidence in Silver Delta tables, runs the SCHADS calculation engine, stores Gold audit results and refreshes AI/BI.
7. Review **AuditHero - SCHADS Payroll Compliance** in AI/BI.
8. Use **AuditHero - Payroll Compliance** in Genie to analyse the governed results.

The source, mapping and output paths are configured as Job defaults. Routine runs normally require only the audit dates.

## Data stored in Databricks

Original and canonical files are retained in the landing Volume. Normalized evidence is stored in Silver tables including employees, employment history, timesheets, payroll earnings and rostered shifts. Audit evidence and reconciliation are stored in Gold tables, with run history stored in `ops.audit_runs`.

Genie queries the governed Gold and semantic layers. It does not perform SCHADS entitlement calculations.

## Employment Hero API

To enable direct extraction:

1. configure the required Databricks Secrets;
2. run **AuditHero - Employment Hero Connection Test (Optional API)**;
3. run **AuditHero - API Audit Readiness (Optional API)**; and
4. use **AuditHero - Monthly Payroll Audit (Optional API)** or **AuditHero - Historical SCHADS Audit (Optional API)**.

API and uploaded-file workflows feed the same Silver, Gold and semantic layers.

## Upgrade

Open `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`, set `release_ref` to the approved version when required, and choose **Run all**.

The upgrade refreshes code, rule packs, Jobs, dashboard, metric views and Genie configuration while preserving historical payroll and audit evidence. Validate a known payroll period after an upgrade before resuming recurring production audits.

## Uninstall

Open `/Shared/AuditHero/admin/AuditHero - Uninstall` and choose **Run all**.

A standard uninstall removes AuditHero Jobs, Genie, dashboard, workspace files and an AuditHero-created SQL warehouse while preserving the AuditHero catalog and evidence.

Permanent catalog deletion requires:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

## CLI / bundle deployment

The repository also includes `databricks.yml` for Declarative Automation Bundle deployment. The UI bootstrap is the documented first-install method; Bundles are available for scripted deployment and CI/CD.
