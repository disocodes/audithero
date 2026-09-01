# Running AuditHero audits

AuditHero supports uploaded-file audits and optional Employment Hero API audits on Microsoft Fabric and Databricks. Both source modes use the same SCHADS calculation engine and result statuses.

## Select the audit workflow

### Organisation-specific CSV/XLSX exports

Use this when source files contain payroll-system-specific field names.

1. Upload the raw exports.
2. Run **AuditHero - Build Source Mapping Workbook** for a new or changed export layout.
3. Review and save the approved mapping as `source_mapping.xlsx`.
4. Run **AuditHero - Convert Mapped Files and Run Audit**.
5. Enter the audit start and end dates.
6. Review the reporting results and any readiness/review findings.

This combined workflow converts source files, runs File Readiness, executes the audit and refreshes reporting.

### Canonical AuditHero files

Use this when `audithero_input.xlsx` or canonical AuditHero CSV/Excel datasets are already available.

- **Microsoft Fabric:** run **AuditHero - Uploaded Files Audit Pipeline**.
- **Databricks:** run **AuditHero - Audit Uploaded CSV Excel**.

The standard uploaded-file workflow runs File Readiness before payroll calculation.

### Conversion and readiness only

Run **AuditHero - Convert Source Files** when mapped source files need to be converted and validated without starting the payroll audit.

### Employment Hero API historical audit

After API connectivity and readiness are validated:

- **Microsoft Fabric:** run **AuditHero - Historical Audit Pipeline**.
- **Databricks:** run **AuditHero - Historical SCHADS Audit (Optional API)**.

Set the required `start_date` and `end_date`. Use actual payroll reconciliation only when the configured payroll source provides the required earnings data.

### Employment Hero API monthly audit

After a representative pay period has been validated:

- **Microsoft Fabric:** use **AuditHero - Monthly Payroll Pipeline**.
- **Databricks:** use **AuditHero - Monthly Payroll Audit (Optional API)**.

Recurring schedules are disabled or paused by default. Enable a schedule only after source mappings, rule selection and representative payroll results have been approved.

## Uploaded-file locations

### Microsoft Fabric

Raw source exports:

`/lakehouse/default/Files/import/raw`

Approved mapping:

`/lakehouse/default/Files/import/source_mapping.xlsx`

Canonical input:

`/lakehouse/default/Files/input`

### Databricks

Raw source exports:

`/Volumes/schads_payroll/bronze/landing/import/raw`

Approved mapping:

`/Volumes/schads_payroll/bronze/landing/import/source_mapping.xlsx`

Canonical input:

`/Volumes/schads_payroll/bronze/landing/input`

## Before the first production audit

Complete the following controls:

1. Setup and Self Test are successful.
2. The required Award/rule dates are present.
3. A representative source mapping is approved.
4. File or API Readiness has no unresolved blocking findings.
5. At least one completed payroll period is independently checked against known payroll outcomes.
6. Representative conditions used by the organisation have been checked, such as weekend work, public holidays, overtime, broken shifts, sleepovers and part-time patterns.

## During an audit

AuditHero records a unique audit run and persists calculation evidence with the results. A run can contain definitive reconciliation statuses and separate review statuses.

`REQUIRES_REVIEW` is not an underpayment. Resolve the identified evidence or rule condition before using the affected period in remediation totals.

## Review results

### Microsoft Fabric

Open **AuditHero - SCHADS Payroll Compliance** in Power BI. Use the detailed audit tables and evidence for investigation.

### Databricks

Open **AuditHero - SCHADS Payroll Compliance** in AI/BI for dashboards and **AuditHero - Payroll Compliance** in Genie for natural-language analysis of governed audit results.

Genie analyses calculated results and semantic measures; it does not determine SCHADS entitlements.

## Rerunning a period

Reruns receive a new audit-run identifier. Historical run evidence remains available. Reporting views expose successful run results according to the platform reporting model.

Document the reason for a rerun when the audit is part of a formal remediation or assurance process.

## Expanding to historical periods

After a known period is validated, expand the audit window in controlled stages. Confirm that effective-dated industrial-instrument coverage, classifications, part-time patterns and other required evidence are available across the full historical range.

See [Understanding AuditHero results](UNDERSTANDING_RESULTS.md) before using audit amounts for remediation or recovery.
