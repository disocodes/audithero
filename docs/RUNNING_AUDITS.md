# Running AuditHero audits

Normal audits are run from **Microsoft Fabric pipelines** or **Databricks Jobs & Pipelines**. The platform UI is the intended operating surface.

## Which workflow should I run?

Use this decision guide:

- Your exports have organisation-specific column names → **AuditHero - Convert Mapped Files and Run Audit**.
- Your files already use AuditHero canonical fields → run the uploaded-file audit directly.
- You only want to test/inspect field conversion → **AuditHero - Convert Source Files**.
- You want AuditHero to pull from Employment Hero automatically → use the optional API workflows after API setup/readiness.

## Mapped source-file audit — normal workflow for most organisations

After `source_mapping.xlsx` has been reviewed and approved, run:

**AuditHero - Convert Mapped Files and Run Audit**

The workflow performs:

```text
raw exports
   ↓
source mapping
   ↓
canonical conversion
   ↓
File Readiness
   ↓
SCHADS audit
   ↓
BI refresh
```

Enter the audit start and end dates in the platform UI. The source, mapping and output paths normally use the standard defaults and only need changing if your administrator chose different folders.

If conversion/readiness fails, the payroll audit does not run. Correct the mapping or source evidence, then rerun the same workflow.

## Canonical uploaded-file audit

Use this path when the input already consists of `audithero_input.xlsx` or canonical AuditHero CSV/Excel files.

### Microsoft Fabric

Run **AuditHero - Uploaded Files Audit Pipeline**.

The pipeline checks the canonical inputs, runs the entitlement engine and publishes the successful result to the Power BI-facing snapshot tables.

### Databricks

Run **AuditHero - Audit Uploaded CSV Excel** from **Jobs & Pipelines**. Set the date range and, if necessary, the input folder in the run parameters.

The job performs File Readiness before payroll calculation and refreshes the dashboard only after the audit succeeds.

## Start with one known payroll period

Do not make the first test a multi-year remediation run. A technically successful large run can still reflect a wrong classification, source mapping or pay-category treatment.

Choose one completed period that payroll/compliance staff can independently check. Include representative conditions actually used by the workforce, for example:

- ordinary weekday work;
- casual Saturday/Sunday/public holiday;
- daily or period overtime;
- broken shift;
- sleepover and active sleepover work;
- part-time agreed pattern/variation;
- shiftwork loading; and
- supplemental or TOIL events where applicable.

Compare the AuditHero calculation evidence with the source records and an independent manual calculation.

## Historical audit

After the known period is validated:

1. load the historical exports/evidence;
2. use the correct mapping version for each export layout;
3. set the historical start/end dates; and
4. run the mapped or canonical uploaded-file workflow again.

Historical work should use effective-dated employment/classification records and industrial-instrument evidence. A current classification or current employment contract is not enough to establish historical Award coverage.

If export formats changed during the historical window, keep separate approved mapping versions and convert the relevant batches with the mapping that matches each layout.

## Optional Employment Hero API audit

API mode uses the same calculation engine after ingestion. Use it only after the optional API Connection Test and API Readiness workflows succeed.

API extraction can reduce repetitive file handling, but it does not eliminate the need for controlled evidence that an API may not establish reliably, such as historical industrial-instrument coverage or written agreement evidence.

## Recurring operation

Recurring schedules should remain paused/disabled until:

- one representative audit period has been independently validated;
- the source mapping is stable;
- required evidence registers/processes are maintained;
- dashboard/reconciliation outputs are understood by the payroll owners; and
- the team knows how `REQUIRES_REVIEW` items are resolved and documented.

A file-based recurring process can still be used without any API: payroll staff replace/upload the latest source exports and run the mapped-import audit pipeline from the UI.

## Re-running a period

Each AuditHero run is identified separately. BI-facing “current” results are intended to reflect the latest successful run rather than a partially failed run.

When rerunning after correcting evidence or a mapping, keep a record of what changed and why, particularly for historical remediation work.
