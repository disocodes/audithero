# Running AuditHero audits

Normal audits are run from Microsoft Fabric pipelines or Databricks Jobs & Pipelines. The examples below describe the UI workflow.

## Uploaded-file audit

This is the recommended starting mode because it does not require API credentials and makes the evidence being audited explicit.

### Before running

1. upload source exports;
2. map/convert them if they are not already canonical;
3. resolve File Readiness blocking findings; and
4. choose the audit date range.

### Fabric

Run **AuditHero - Uploaded Files Audit Pipeline**.

The pipeline validates the canonical inputs, executes the shared entitlement engine, writes the audit outputs and then refreshes the BI-facing snapshot after a successful run.

### Databricks

Run **AuditHero - Audit Uploaded CSV Excel** from Jobs & Pipelines. Enter `input_root`, `start_date` and `end_date` in the run parameters when needed.

The job runs File Readiness first, then the audit and dashboard refresh.

## Why you should validate one known period first

A technically successful multi-year run can still be wrong for your organisation if classifications, pay-category treatment, industrial-instrument history or source mappings are wrong. A known period gives payroll/compliance staff a manageable sample to compare manually.

Recommended validation cases include the actual conditions your workforce uses, such as:

- ordinary weekday shift;
- casual weekend/public holiday;
- overtime threshold;
- broken shift;
- sleepover and active sleepover work;
- part-time agreed pattern/variation;
- shiftwork loading; and
- supplemental/TOIL event if applicable.

## Historical audit

Once the known period is validated, set the full start/end dates and rerun the uploaded-file audit. Keep the same approved source mapping for exports with the same structure; version the mapping if the source layout changed historically.

Historical remediation should not rely on a single current classification or current contract. Supply effective-dated employment/classification and industrial-instrument evidence.

## Optional API audit

API mode uses the same calculation engine after ingestion. Use it only after API Connection Test and API Readiness complete successfully.

API mode is useful for recurring extraction, but it does not remove the need to maintain controlled evidence that an API cannot reliably establish (for example historical industrial-instrument coverage or written agreement evidence).

## Monthly operation

The recurring monthly workflow should start paused/disabled. Enable it only after:

- a representative file/API run succeeds;
- source mapping is stable;
- required evidence registers are maintained;
- dashboard/reconciliation results are signed off; and
- the appropriate payroll owners know how to handle `REQUIRES_REVIEW`.

## Re-running the same period

AuditHero writes each run with an audit run identifier and run timestamps. BI-facing “current” outputs should represent the latest successful run rather than a partially failed run.

When rerunning after correcting data, keep evidence of what changed and why, especially for remediation work.
