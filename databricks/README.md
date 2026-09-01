# AuditHero on Databricks

AuditHero is operated through Databricks **Jobs & Pipelines**, **Catalog Explorer**, **AI/BI**, and **Genie**.

## Installation

Import `installers/Databricks_Install_AuditHero.py` into the target workspace and choose **Run all**.

A successful installation creates or updates the AuditHero workspace files, Jobs, Unity Catalog structures, landing Volume, Silver and Gold Delta tables, semantic metric views, AI/BI dashboard, and Genie space. Installation finishes by running Setup and Self Test.

Administration notebooks are installed at:

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

Employment Hero credentials are required only for Employment Hero API workflows.

## First CSV/Excel audit

1. Export the required payroll, HR, rostering, and timekeeping CSV/XLSX files.
2. Upload the original exports to `/Volumes/schads_payroll/bronze/landing/import/raw`.
3. Run **AuditHero - Build Source Mapping Workbook** for a new or changed source layout.
4. Review `source_mapping_draft.xlsx`.
5. Save the approved mapping as `/Volumes/schads_payroll/bronze/landing/import/source_mapping.xlsx`.
6. Run **AuditHero - Convert Mapped Files and Run Audit**.
7. Enter the audit start and end dates.
8. Review **AuditHero - SCHADS Payroll Compliance** in AI/BI.
9. Use **AuditHero - Payroll Compliance** in Genie for governed analysis of completed audit results.

The standard Job configuration already contains the default Volume paths. Routine file audits normally require only the audit dates unless a source or storage location has changed.

## File-audit processing flow

```text
Raw CSV/XLSX exports
        ↓
Approved source mapping
        ↓
Canonical conversion
        ↓
File Readiness
        ↓
Silver normalized evidence
        ↓
SCHADS calculation engine
        ↓
Gold audit results
        ↓
Unity Catalog metric views
        ↓
AI/BI and Genie
```

If File Readiness identifies a blocking issue, the payroll calculation does not proceed until the blocking issue is resolved.

## Stored data

Normalized source evidence is stored in Silver tables such as:

- `schads_payroll.silver.employees`
- `schads_payroll.silver.employment_history`
- `schads_payroll.silver.timesheets`
- `schads_payroll.silver.payroll_earnings`
- `schads_payroll.silver.rostered_shifts`

Audit outputs are stored in:

- `schads_payroll.gold.audit_detail`
- `schads_payroll.gold.pay_period_reconciliation`
- `schads_payroll.gold.audit_event_adjustments`
- `schads_payroll.gold.toil_findings`
- `schads_payroll.ops.audit_runs`

Governed reporting uses:

- `schads_payroll.semantic.payroll_compliance`
- `schads_payroll.semantic.audit_detail`

Genie queries governed AuditHero results and semantic measures. SCHADS entitlement calculations are performed by the AuditHero calculation engine before results reach the reporting layer.

## Routine monthly file audit

After a mapping has been approved for the source layout:

1. upload the new exports to the raw import folder;
2. run **AuditHero - Convert Mapped Files and Run Audit**;
3. enter the audit dates; and
4. review AI/BI, Genie, and detailed audit evidence.

Rebuild the source mapping when the source-system export structure, sheet names, columns, or coded values change.

## Canonical AuditHero files

If the source files already use the AuditHero canonical format, upload them to:

`/Volumes/schads_payroll/bronze/landing/input`

Then run:

**AuditHero - Audit Uploaded CSV Excel**

## Employment Hero API

After the required Databricks Secrets are configured:

1. run **AuditHero - Employment Hero Connection Test (Optional API)**;
2. run **AuditHero - API Audit Readiness (Optional API)**;
3. use **AuditHero - Monthly Payroll Audit (Optional API)** for recurring audits; or
4. use **AuditHero - Historical SCHADS Audit (Optional API)** for a selected historical range.

API and uploaded-file workflows use the same calculation and governed result layers.

## Upgrade

Open `/Shared/AuditHero/admin/AuditHero - Install or Upgrade` and choose **Run all**.

After an upgrade, validate a known payroll period before resuming recurring production audits.

## Uninstall

Open `/Shared/AuditHero/admin/AuditHero - Uninstall` and choose **Run all**.

A standard uninstall preserves the AuditHero catalog and stored evidence. Permanent data removal requires the exact confirmation phrase `DELETE AUDITHERO DATA`.

## Documentation

- [Quick start](../QUICKSTART.md)
- [Databricks installation](../docs/INSTALL_DATABRICKS_UI.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
