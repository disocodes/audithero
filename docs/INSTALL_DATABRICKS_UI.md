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
- administration notebooks;
- AuditHero Jobs;
- a SQL warehouse when required and permitted;
- **AuditHero - SCHADS Payroll Compliance** in AI/BI;
- the configured Unity Catalog and `bronze`, `silver`, `ref`, `gold`, `ops`, and `semantic` schemas;
- the `bronze.landing` Volume and file landing locations;
- effective-dated SCHADS reference tables;
- Silver normalized-evidence tables;
- Gold audit-result tables;
- governed semantic metric views; and
- **AuditHero - Payroll Compliance** in Genie.

Installation finishes by running Setup and Self Test.

## First installation

1. Import `installers/Databricks_Install_AuditHero.py` into the target workspace.
2. Review the installation settings.
3. Choose **Run all**.
4. Confirm Setup and Self Test complete successfully before using production payroll evidence.

Default settings include:

```python
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
existing_cluster_id = ""
```

Leave `existing_cluster_id` blank to use serverless Jobs where supported. Leave the monthly audit schedule paused until a representative period has been validated.

## First CSV / Excel audit

### 1. Upload source evidence

Upload unchanged source files to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

Do not rename/rearrange columns solely to satisfy AuditHero.

### 2. Preview and prepare

Run:

**AuditHero - Preview Uploaded Files**

Review the displayed interpretation and the generated:

`/Volumes/schads_payroll/bronze/landing/auto_input/auto_intake_preview.csv`

AuditHero does not start the audit during this step.

### 3. Continue or correct

If the interpretation is correct, run:

**AuditHero - Audit Reviewed Uploaded Files**

The audit reads the prepared canonical files and uses `auto_intake_manifest.json` to determine the prepared audit window unless dates are explicitly overridden.

If the interpretation is incorrect or incomplete, run:

**AuditHero - Build Source Mapping Workbook (Advanced)**

Review the generated `source_mapping_draft.xlsx`, correct controlled file-role/field/value selections, save it as `source_mapping.xlsx`, then run:

**AuditHero - Convert Mapped Files and Run Audit (Advanced)**

### 4. Review results

Open:

- **AI/BI → AuditHero - SCHADS Payroll Compliance**; and/or
- **Genie → AuditHero - Payroll Compliance**.

Genie queries governed calculated results; it does not independently calculate SCHADS entitlements.

## Advanced conversion/readiness only

Run **AuditHero - Convert Source Files (Advanced)** when mapped source files need to be converted and checked without starting payroll calculation.

Run **AuditHero - File Readiness (Advanced)** to assess canonical evidence already in the input folder.

## Canonical AuditHero files

Canonical inputs are stored under:

`/Volumes/schads_payroll/bronze/landing/input`

Use **AuditHero - Audit Canonical CSV Excel (Advanced)** when canonical files have already been prepared and the audit window is known.

## Routine monthly CSV / Excel process

For each period:

1. archive/retain the original evidence batch;
2. upload the new raw batch;
3. run **AuditHero - Preview Uploaded Files**;
4. review the interpretation/warnings;
5. run **AuditHero - Audit Reviewed Uploaded Files** if correct, or use Advanced Mapping if required; and
6. review dashboard, Genie and detailed evidence findings.

Rebuild/review mapping when the source-system report structure or payroll-category coding changes.

## Data stored in Databricks

The landing Volume stores source/prepared/canonical files. Silver tables store normalized source evidence. Gold tables store calculated audit evidence and reconciliation. `ops.audit_runs` records execution history. The `semantic` schema exposes governed metrics to AI/BI and Genie.

## Employment Hero API

To enable direct extraction:

1. configure the required Databricks Secrets;
2. run **AuditHero - Employment Hero Connection Test (Optional API)**;
3. run **AuditHero - API Audit Readiness (Optional API)**; and
4. use **AuditHero - Monthly Payroll Audit (Optional API)** or **AuditHero - Historical SCHADS Audit (Optional API)**.

The monthly schedule is paused by default.

## Upgrade

Open `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`, set `release_ref` to the approved release, and choose **Run all**.

Validate a known payroll period after an upgrade before resuming recurring production audits.

## Uninstall

Open `/Shared/AuditHero/admin/AuditHero - Uninstall` and choose **Run all**.

A standard uninstall preserves the AuditHero catalog and payroll/audit storage. Permanent data removal requires:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```
