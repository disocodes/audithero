# AuditHero on Databricks

AuditHero is operated through **Databricks Jobs & Pipelines, Catalog Explorer, AI/BI dashboards and Genie**. The SCHADS calculation engine, rule library, source data, audit evidence and reporting assets remain inside the Databricks environment.

## First installation

In **Workspace → Import → URL**, import the public raw URL for `installers/Databricks_Install_AuditHero.py`, open the notebook and choose **Run all**.

The installer creates or updates:

- `/Shared/AuditHero` workspace files and managed notebooks;
- AuditHero Jobs;
- the Unity Catalog `schads_payroll` catalog, schemas and landing Volume;
- effective-dated SCHADS reference tables;
- Silver normalized-evidence tables and Gold audit-result tables;
- `schads_payroll.semantic.payroll_compliance` and `schads_payroll.semantic.audit_detail` metric views;
- the published **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard; and
- the **AuditHero - Payroll Compliance** Genie space.

Setup and Self Test run during installation. The administration notebooks are installed at:

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

Employment Hero credentials are optional. Uploaded-file auditing works without them.

## CSV / Excel audit workflow

1. Export CSV/XLSX files from the payroll, HR, rostering or timekeeping systems.
2. In **Catalog Explorer**, upload them to `/Volumes/schads_payroll/bronze/landing/import/raw`.
3. For a new export layout, run **AuditHero - Build Source Mapping Workbook**.
4. Review `source_mapping_draft.xlsx` and save the approved mapping as `source_mapping.xlsx` in `/Volumes/schads_payroll/bronze/landing/import`.
5. Run **AuditHero - Convert Mapped Files and Run Audit** and enter the required audit start and end dates.
6. The Job converts the source files to canonical AuditHero data, runs File Readiness, stores normalized evidence in Silver Delta tables, executes the SCHADS audit, stores the results in Gold Delta tables and refreshes AI/BI.
7. Review **AuditHero - SCHADS Payroll Compliance** in AI/BI.
8. Open **AuditHero - Payroll Compliance** in Genie for natural-language analysis of the governed results.

The standard Volume paths are already configured as Job defaults. Routine runs normally require only the audit dates.

### Data retained in Databricks

Original and canonical files remain in the Unity Catalog Volume. Normalized evidence is appended to tables such as:

- `schads_payroll.silver.employees`
- `schads_payroll.silver.employment_history`
- `schads_payroll.silver.timesheets`
- `schads_payroll.silver.payroll_earnings`
- `schads_payroll.silver.rostered_shifts`

Audit results are appended to:

- `schads_payroll.gold.audit_detail`
- `schads_payroll.gold.pay_period_reconciliation`
- `schads_payroll.gold.audit_event_adjustments`
- `schads_payroll.gold.toil_findings`
- `schads_payroll.ops.audit_runs`

Genie queries governed Gold and semantic assets. SCHADS entitlement calculations are performed by the AuditHero calculation engine before the results are made available to Genie.

## Subsequent monthly file audits

After a source mapping has been approved, the recurring workflow is:

`upload new exports → run Convert Mapped Files and Run Audit → review AI/BI and Genie`

Run **AuditHero - File Readiness** separately when canonical files need to be checked without starting the audit.

## Employment Hero API workflow

After Databricks Secrets are configured:

1. run **AuditHero - Employment Hero Connection Test (Optional API)**;
2. run **AuditHero - API Audit Readiness (Optional API)**;
3. run **AuditHero - Monthly Payroll Audit (Optional API)** for recurring API audits; or
4. run **AuditHero - Historical SCHADS Audit (Optional API)** with a start and end date for historical audits.

API and uploaded-file workflows write to the same Silver, Gold and semantic layers, so they use the same dashboard and Genie experience.

## Upgrade

Open `/Shared/AuditHero/admin/AuditHero - Install or Upgrade` and choose **Run all**. The upgrade refreshes AuditHero code, rule packs, Jobs, dashboard, metric views and Genie configuration while preserving historical payroll and audit evidence.

## Uninstall

Open `/Shared/AuditHero/admin/AuditHero - Uninstall` and choose **Run all**.

A standard uninstall removes AuditHero Jobs, Genie, dashboard, workspace files and any SQL warehouse created specifically by AuditHero while preserving the AuditHero catalog and evidence. Permanent data removal requires the exact confirmation phrase `DELETE AUDITHERO DATA`.

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Install, upgrade and remove](../docs/INSTALL_DATABRICKS_UI.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)
