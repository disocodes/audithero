# Install AuditHero in Databricks

AuditHero can be installed from the **Databricks workspace UI** with one bootstrap notebook. A separate frontend app is not required.

## What the installer creates

The installer creates or updates:

- `/Shared/AuditHero` workspace code/notebooks;
- managed Install/Upgrade and Uninstall notebooks;
- all AuditHero Jobs;
- a SQL warehouse for AI/BI when no suitable warehouse exists and permissions allow creation;
- the published **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard;
- the `schads_payroll` Unity Catalog, schemas and landing Volume;
- effective-dated SCHADS reference tables;
- Silver normalized-evidence and Gold audit-result structures;
- governed Unity Catalog metric views under `schads_payroll.semantic`; and
- the **AuditHero - Payroll Compliance** Genie Agent.

It then runs **AuditHero - Setup** and the SCHADS self-test path automatically.

Employment Hero credentials are not required for installation or uploaded CSV/Excel audits.

## Requirements

You need a Databricks workspace with:

- Unity Catalog;
- permission to run notebooks and Jobs;
- permission to create or use the configured AuditHero catalog;
- access to a SQL warehouse; and
- Genie enabled if you want the natural-language analysis surface.

The current semantic metric views require a Databricks runtime/SQL environment that supports Unity Catalog metric views (`CREATE VIEW ... WITH METRICS`).

## First installation

### 1. Import the bootstrap notebook

In Databricks:

1. open **Workspace**;
2. choose **Import**;
3. choose **URL**;
4. use the raw GitHub URL for `installers/Databricks_Install_AuditHero.py` from the approved release;
5. open the imported notebook.

### 2. Review settings

Normal defaults are:

```python
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
existing_cluster_id = ""
```

Leave `sql_warehouse_id` blank to allow AuditHero to use an available SQL warehouse or create `AuditHero SQL Warehouse` when permitted.

Leave `existing_cluster_id` blank to use serverless Jobs where supported.

### 3. Run all

The installer:

1. authenticates as the current Databricks session;
2. downloads the selected AuditHero release;
3. installs workspace files/notebooks;
4. selects or creates the SQL warehouse;
5. creates/publishes the AI/BI dashboard;
6. creates or updates AuditHero Jobs;
7. runs Setup;
8. Setup creates the catalog, Volume, Delta structures, rule tables, Gold views and Unity Catalog metric views;
9. Setup creates/updates the AuditHero Genie Agent after those trusted assets exist;
10. validation/self-test tasks run; and
11. installation state is saved for safe removal.

Do not use production payroll data if Setup or Self Test fails.

## After installation: uploaded CSV/Excel workflow

1. Export the payroll/HR/timekeeping CSV or Excel files.
2. In **Catalog Explorer**, upload them to:
   `/Volumes/schads_payroll/bronze/landing/import/raw`
3. For a new export layout, run **AuditHero - Build Source Mapping Workbook**.
4. Review `source_mapping_draft.xlsx` and upload the approved mapping as:
   `/Volumes/schads_payroll/bronze/landing/import/source_mapping.xlsx`
5. Run **AuditHero - Convert Mapped Files and Run Audit** and enter the audit start/end dates.
6. AuditHero converts the source files, runs File Readiness, appends normalized evidence to Silver Delta tables, runs the deterministic SCHADS engine, appends Gold audit outputs and refreshes AI/BI.
7. Review **AuditHero - SCHADS Payroll Compliance** in AI/BI.
8. Use **AuditHero - Payroll Compliance** in Genie for natural-language analysis of the governed results.

The source/mapping/output paths are already populated as Job defaults. Normal operators usually only change the audit dates.

## What goes into Databricks

The original/canonical files are retained in the landing Volume. Normalized evidence is stored in Silver tables including employees, employment history, timesheets, payroll earnings and rostered shifts. Audit evidence/results are stored in Gold tables including audit detail, pay-period reconciliation, supplemental adjustments and TOIL findings. Run history is stored in `ops.audit_runs`.

Genie queries Gold and semantic assets. It is not part of the SCHADS calculation engine and must not be used to decide entitlements itself.

## Employment Hero API

If direct extraction is configured later:

1. configure Databricks Secrets;
2. run **AuditHero - Employment Hero Connection Test (Optional API)**;
3. run **AuditHero - API Audit Readiness (Optional API)**;
4. use **AuditHero - Monthly Payroll Audit (Optional API)** or **AuditHero - Historical SCHADS Audit (Optional API)**.

API and file workflows feed the same Silver/Gold/semantic layer.

## Upgrade

Open `/Shared/AuditHero/admin/AuditHero - Install or Upgrade` and choose **Run all**. The upgrade refreshes code, rule packs, Jobs, dashboard, metric views and Genie configuration without deleting historical evidence.

## Uninstall

Open `/Shared/AuditHero/admin/AuditHero - Uninstall` and choose **Run all**.

Normal uninstall removes AuditHero Jobs, Genie, dashboard/code and an AuditHero-created SQL warehouse while preserving the catalog and evidence. Permanent catalog deletion requires:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

## CLI / bundle deployment

The repository also includes `databricks.yml` for Declarative Automation Bundles. It uses the direct deployment engine and requires Databricks CLI 1.3.0 or newer. The UI bootstrap remains the simplest first-install path for a normal operator/admin.
