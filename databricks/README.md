# AuditHero on Databricks

AuditHero is installed, upgraded and operated from Databricks. There is **no separate AuditHero app** and normal payroll users do not need to work in notebooks.

## First installation

In **Workspace → Import → URL**, import the public raw URL for `installers/Databricks_Install_AuditHero.py`, open it and choose **Run all**.

The installer creates or updates:

- `/Shared/AuditHero` workspace code and managed notebooks;
- AuditHero Jobs;
- the Unity Catalog `schads_payroll` catalog, schemas and landing Volume;
- effective-dated SCHADS reference tables;
- Silver normalized evidence tables and Gold audit-result structures;
- `schads_payroll.semantic.payroll_compliance` and `schads_payroll.semantic.audit_detail` metric views;
- the published **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard; and
- the **AuditHero - Payroll Compliance** Genie Agent.

Setup and Self Test run automatically. The installed administration notebooks are:

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

Employment Hero credentials are optional. Uploaded-file auditing works without them.

## Normal CSV / Excel workflow

After AuditHero is deployed:

1. Export CSV/XLSX files from payroll, HR, rostering or timekeeping systems.
2. In **Catalog Explorer**, upload them to:
   `/Volumes/schads_payroll/bronze/landing/import/raw`
3. For a new export layout, run **AuditHero - Build Source Mapping Workbook**.
4. Review `source_mapping_draft.xlsx`, save the approved mapping as `source_mapping.xlsx` in the import folder.
5. Run **AuditHero - Convert Mapped Files and Run Audit** and enter the audit start/end dates.
6. The job converts the files to canonical AuditHero data, performs File Readiness, loads normalized evidence into Silver Delta tables, executes the SCHADS engine, writes Gold audit results and refreshes AI/BI.
7. Open **AuditHero - SCHADS Payroll Compliance** in AI/BI for the dashboard.
8. Open **AuditHero - Payroll Compliance** in Genie to ask natural-language questions about the governed results.

The standard paths are already the Job defaults, so operators normally change only the audit dates.

### What is persisted

Original/canonical files remain in the Unity Catalog Volume. Normalized evidence is appended to tables such as:

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

Genie does not calculate SCHADS entitlements. It queries governed Gold/semantic results produced by the deterministic AuditHero engine.

## Subsequent monthly file audits

Once a source mapping is approved, the recurring workflow is simply:

`upload new exports → run Convert Mapped Files and Run Audit → review AI/BI / Genie`

Use **AuditHero - File Readiness** separately only when you want to validate canonical files before an audit.

## Employment Hero API workflow

After Databricks Secrets are configured:

1. run **AuditHero - Employment Hero Connection Test (Optional API)** once;
2. run **AuditHero - API Audit Readiness (Optional API)**;
3. run **AuditHero - Monthly Payroll Audit (Optional API)** for recurring audits; or
4. run **AuditHero - Historical SCHADS Audit (Optional API)** with a start/end date for historical work.

The API workflows write to the same Silver/Gold/semantic model as file-based audits, so the dashboard and Genie experience is the same.

## Upgrade

Open `/Shared/AuditHero/admin/AuditHero - Install or Upgrade` and choose **Run all**. Setup is idempotent: it refreshes rules, semantic metric views, Jobs, dashboard and Genie configuration without deleting historical payroll/audit evidence.

## Uninstall

Open `/Shared/AuditHero/admin/AuditHero - Uninstall` and choose **Run all**.

Normal uninstall removes Jobs, Genie, dashboard/code and any SQL warehouse created specifically by AuditHero while preserving the AuditHero catalog and evidence. Permanent data removal requires the exact confirmation phrase `DELETE AUDITHERO DATA`.

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Install, upgrade and remove](../docs/INSTALL_DATABRICKS_UI.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Optional CLI/automation](../docs/CLI_AND_AUTOMATION.md)
