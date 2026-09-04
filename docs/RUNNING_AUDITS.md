# Running AuditHero audits

AuditHero supports reviewed uploaded-file audits and optional Employment Hero API audits on Microsoft Fabric and Databricks. Both source modes use the shared SCHADS calculation engine and effective-dated rule library.

## Standard uploaded-file workflow

Use this for ordinary CSV/XLSX exports.

### Step 1 — Upload source evidence

Upload the original source files without editing them.

**Microsoft Fabric**

`/lakehouse/default/Files/import/raw`

**Databricks**

`/Volumes/schads_payroll/bronze/landing/import/raw`

### Step 2 — Preview the interpretation

Run **AuditHero - Preview Uploaded Files**.

The preview/preparation step:

- scans supported CSV/XLSX files and Excel sheets;
- identifies recognisable timesheet, employee/rate and payroll earning evidence;
- writes prepared canonical candidate files;
- writes `auto_intake_preview.csv`;
- writes `auto_intake_manifest.json`; and
- reports evidence warnings without running entitlement calculation.

Review the detected file roles and mapped source fields before proceeding.

### Step 3 — Choose the correct path

If the automatic interpretation is correct, run **AuditHero - Audit Reviewed Uploaded Files**.

If a file role, source field or value interpretation is incorrect, run **AuditHero - Build Source Mapping Workbook (Advanced)**, approve the correction/context workbook, then run **AuditHero - Convert Mapped Files and Run Audit (Advanced)**.

Advanced Mapping is not required merely because multiple files or Excel sheets were uploaded.

## Advanced mapped-file workflow

Use the Advanced Mapping workflow when a source layout cannot be interpreted safely or when additional file context is required.

1. Upload raw exports to the standard raw folder.
2. Run **AuditHero - Build Source Mapping Workbook (Advanced)**.
3. Review `preview` first.
4. Correct `file_context`, `field_mapping`, `value_mapping`, and `pay_category_treatment` where applicable.
5. Save/upload the approved workbook as `source_mapping.xlsx`.
6. Run **AuditHero - Convert Mapped Files and Run Audit (Advanced)**.
7. Review readiness, calculation results and evidence findings.

The approved mapping does not replace source evidence. `mapping_used.json` records the interpretation used for conversion.

## Canonical-file workflow

Use this when canonical AuditHero CSV files or `audithero_input.xlsx` already exist.

- Run File Readiness before calculation.
- Resolve blocking findings for workflows requiring full readiness.
- Run the canonical-file audit with an explicit audit window.

Canonical inputs should not be manually altered after readiness without re-running readiness and documenting the change.

## Actual-pay reconciliation

Expected entitlement analysis and actual-pay reconciliation are separate capabilities.

Actual-pay reconciliation requires payroll earning evidence containing:

- employee identifier;
- pay-period start;
- pay-period end;
- pay category; and
- amount.

Every pay category used in the comparator must also have an approved treatment. Missing payroll amounts remain missing evidence; they are not interpreted as zero paid.

If payroll evidence is incomplete, expected entitlement analysis can still proceed where the underlying employee and shift evidence is sufficient, but the result must not be presented as a confirmed actual-pay variance.

## File Readiness

Readiness validates more than file names and headers. It checks required values, date/time conversions, identifier uniqueness, employee-key relationships, shift intervals, classification evidence, industrial-instrument controls, part-time evidence where applicable, and actual-pay controls.

A readable file is not necessarily an audit-ready file.

## Employment Hero API historical audit

After API connectivity and readiness are validated:

- **Microsoft Fabric:** run the deployed Historical Audit pipeline.
- **Databricks:** run **AuditHero - Historical SCHADS Audit (Optional API)**.

Set the required `start_date` and `end_date`. Use actual-pay reconciliation only when the configured payroll API path supplies usable earnings evidence and controlled pay-category treatment.

## Employment Hero API monthly audit

After a representative period has been validated:

- **Microsoft Fabric:** use the deployed Monthly Payroll pipeline.
- **Databricks:** use **AuditHero - Monthly Payroll Audit (Optional API)**.

Recurring schedules are disabled or paused by default. Enable recurring execution only after source mappings, rule selection, controlled evidence and representative results have been approved.

## Before the first production audit

Complete these controls:

1. Setup and Self Test are successful in the target platform.
2. The required Award/rule dates and classification families are present in the installed rule manifest.
3. The source-file interpretation is reviewed for a representative batch.
4. File or API Readiness has no unresolved blocking findings for the intended workflow.
5. Industrial-instrument coverage has been established for the period under review.
6. Part-time pattern/variation evidence is available where required.
7. Payroll earning categories have approved treatment before actual-pay reconciliation is relied on.
8. At least one completed payroll period is independently checked against known source documents and payroll outcomes.
9. Representative conditions used by the organisation have been checked, including relevant weekend, public-holiday, overtime, rest, meal-break, broken-shift, sleepover, allowance and TOIL scenarios.

## During an audit

AuditHero records a unique audit run and persists calculation evidence with the results. A run can contain definitive reconciliation statuses and separate review statuses.

`REQUIRES_REVIEW` is not a confirmed underpayment. Resolve the identified evidence or coverage issue before including the affected period in remediation totals.

## Review results

### Microsoft Fabric

Open **AuditHero - SCHADS Payroll Compliance** in Power BI and inspect both summary measures and detailed calculation/evidence records.

### Databricks

Open **AuditHero - SCHADS Payroll Compliance** in AI/BI for dashboards and **AuditHero - Payroll Compliance** in Genie for analysis of governed calculated results.

Genie analyses persisted calculations and semantic measures; it does not determine SCHADS entitlements independently.

## Rerunning a period

Reruns receive a new audit-run identifier. Historical evidence remains available and reporting exposes successful runs according to the platform reporting model.

For formal assurance/remediation work, record why the rerun occurred, the evidence changed, and who approved the revised inputs/mapping.

## Expanding to historical periods

Expand the audit window in controlled stages after a known representative period is validated. Confirm effective-dated coverage across the entire historical window, including:

- industrial instrument;
- employment type;
- classification and pay point;
- work group;
- employee rate history;
- part-time patterns/variations;
- location/public-holiday evidence; and
- relevant payroll and supplemental control registers.

See [Understanding AuditHero results](UNDERSTANDING_RESULTS.md) before using audit amounts for remediation or recovery.
