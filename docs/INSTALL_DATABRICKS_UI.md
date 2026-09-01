# Install AuditHero in Databricks

This guide covers installation, first use, upgrade, and removal of AuditHero in a Databricks workspace.

## Requirements

The target workspace must provide:

- Unity Catalog;
- permission to run notebooks and Jobs;
- permission to create or use the configured AuditHero catalog;
- access to a SQL warehouse; and
- Genie access when natural-language analysis will be used.

Employment Hero credentials are required only for Employment Hero API workflows.

## Resources created by the installer

The installer creates or updates:

- `/Shared/AuditHero` workspace files and notebooks;
- **AuditHero - Install or Upgrade** and **AuditHero - Uninstall** administration notebooks;
- AuditHero Jobs;
- a SQL warehouse when required and permitted;
- the **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard;
- the `schads_payroll` Unity Catalog;
- the `bronze`, `silver`, `ref`, `gold`, `ops`, and `semantic` schemas;
- the `bronze.landing` Unity Catalog Volume;
- `/Volumes/schads_payroll/bronze/landing/import/raw`;
- `/Volumes/schads_payroll/bronze/landing/input`;
- effective-dated SCHADS reference tables;
- Silver normalized-evidence tables;
- Gold audit-result tables;
- governed metric views under `schads_payroll.semantic`; and
- the **AuditHero - Payroll Compliance** Genie space.

Installation finishes by running **AuditHero - Setup** and **AuditHero - Self Test**.

## First installation

### 1. Import the installer notebook

In Databricks:

1. open **Workspace**;
2. choose **Import**;
3. choose **URL**;
4. enter the raw GitHub URL for `installers/Databricks_Install_AuditHero.py`; and
5. open the imported notebook.

### 2. Review the installation settings

The default settings are:

```python
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
existing_cluster_id = ""
```

Leave `sql_warehouse_id` blank to use an available SQL warehouse or to create **AuditHero SQL Warehouse** when permissions allow it.

Leave `existing_cluster_id` blank to use serverless Jobs where supported. If serverless Jobs are unavailable, enter a compatible existing cluster ID.

### 3. Run the installer

Choose **Run all**.

A successful installation finishes with Setup and Self Test reported as successful.

Do not use production payroll data when Setup or Self Test has failed.

## First CSV/Excel audit

### 1. Export source files

Export the required payroll, HR, rostering, and timekeeping CSV/XLSX files.

Keep the original export structure. Do not rename or rearrange columns solely to match AuditHero.

### 2. Upload the files

In **Catalog Explorer**, upload the files to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

### 3. Build a source mapping

For a new or changed source layout, run:

**AuditHero - Build Source Mapping Workbook**

The Job uses the standard raw import folder and creates:

`/Volumes/schads_payroll/bronze/landing/import/source_mapping_draft.xlsx`

### 4. Review and approve the mapping

Review the draft workbook and confirm:

- source file and sheet selection;
- field mappings;
- joins between datasets;
- default or constant values;
- value translations; and
- required fields for the audit.

Save the approved workbook as:

`/Volumes/schads_payroll/bronze/landing/import/source_mapping.xlsx`

### 5. Run the audit

Run:

**AuditHero - Convert Mapped Files and Run Audit**

Enter the audit start and end dates. The standard source, mapping, and output paths are already configured in the Job.

The Job:

1. converts the approved source files to AuditHero canonical datasets;
2. writes canonical files to `/Volumes/schads_payroll/bronze/landing/input`;
3. runs File Readiness;
4. stops if blocking evidence issues remain;
5. loads normalized source evidence to Silver Delta tables;
6. calculates expected SCHADS entitlements;
7. reconciles expected and actual auditable pay where sufficient payroll earnings are available;
8. writes Gold audit results and operational run history; and
9. refreshes the AI/BI dashboard.

### 6. Review results

Open:

**AI/BI → AuditHero - SCHADS Payroll Compliance**

Use the dashboard for payroll totals, exceptions, trends, and audit-run review.

Open:

**Genie → AuditHero - Payroll Compliance**

Use Genie for governed questions about completed audit results, such as:

- Which employees have underpaid pay periods?
- Which pay periods require review?
- What is the potential underpayment for the latest successful audit?
- Which classifications have the most review findings?

Genie queries governed Gold and semantic assets. SCHADS entitlement calculations are performed by the AuditHero calculation engine before results reach Genie.

## Routine monthly CSV/Excel audit

After the source layout has an approved mapping:

1. export the latest source files;
2. upload them to `/Volumes/schads_payroll/bronze/landing/import/raw`;
3. run **AuditHero - Convert Mapped Files and Run Audit**;
4. enter the audit dates; and
5. review AI/BI, Genie, and detailed audit evidence.

Rebuild the source mapping when the source-system export structure changes.

## Canonical AuditHero files

If files already use the AuditHero canonical workbook/CSV structure, upload them to:

`/Volumes/schads_payroll/bronze/landing/input`

Then run:

**AuditHero - Audit Uploaded CSV Excel**

No source-mapping step is required.

## Data stored in Databricks

The landing Volume retains source and canonical files used by the workflow.

Silver tables store normalized source evidence such as:

- employees;
- employment history;
- pay details;
- timesheets;
- rostered shifts;
- payroll earnings; and
- public-holiday data.

Gold tables store calculated audit evidence and reconciliation results. `ops.audit_runs` records audit execution history.

The `semantic` schema contains governed metric views used by AI/BI and Genie.

## Employment Hero API

To enable direct extraction:

1. configure the required Databricks Secrets;
2. run **AuditHero - Employment Hero Connection Test (Optional API)**;
3. run **AuditHero - API Audit Readiness (Optional API)**; and
4. use **AuditHero - Monthly Payroll Audit (Optional API)** or **AuditHero - Historical SCHADS Audit (Optional API)**.

The API and uploaded-file workflows use the same calculation and governed result layers.

## Upgrade

Open:

`/Shared/AuditHero/admin/AuditHero - Install or Upgrade`

Set `release_ref` to the approved release when required and choose **Run all**.

The upgrade refreshes managed code, rule packs, Jobs, reporting assets, and Genie configuration while preserving the AuditHero catalog and historical evidence.

Validate a known payroll period after an upgrade before resuming recurring production audits.

## Uninstall

Open:

`/Shared/AuditHero/admin/AuditHero - Uninstall`

A standard uninstall removes managed AuditHero workspace resources while preserving the AuditHero catalog and stored evidence.

Permanent catalog deletion requires:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

## Bundle and CLI deployment

The repository includes `databricks.yml` for Databricks Declarative Automation Bundle deployment. Use Bundle/CLI deployment for scripted administration or CI/CD where appropriate.
