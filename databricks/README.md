# AuditHero on Databricks

AuditHero is operated through Databricks **Jobs & Pipelines**, **Catalog Explorer**, **AI/BI**, and **Genie**.

## Installation

Import `installers/Databricks_Install_AuditHero.py` into the target workspace and choose **Run all**.

A successful installation creates or updates the AuditHero workspace files, Jobs, Unity Catalog structures, landing Volume, Silver and Gold Delta tables, semantic metric views, AI/BI dashboard, and Genie space.

Administration notebooks are installed at:

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

Employment Hero credentials are required only for Employment Hero API workflows.

## Standard CSV/Excel audit

1. Upload ordinary CSV/XLSX files to `/Volumes/schads_payroll/bronze/landing/import/raw`.
2. Run **AuditHero - Preview Uploaded Files** and review the detected file roles, date range and prepared evidence.
3. If the preview is correct, run **AuditHero - Audit Reviewed Uploaded Files** for the required date range.
4. Open **AuditHero - SCHADS Payroll Compliance** in AI/BI.
5. Use **AuditHero - Payroll Compliance** in Genie for governed natural-language analysis.

Automatic intake can combine information across multiple files and workbook sheets. A basic timesheet needs an employee name or identifier plus shift start and end. Additional information is used when available, including hours, break minutes, hourly rates, effective dates, employment type, classification, location, work type, pay-period dates and explicit actual amounts.

The Preview job prepares only the selected audit window when dates are supplied. Operator-entered Australian dates are day-first, for example `01-05-2025` means **1 May 2025**.

## Effective-dated rate history

Employee hourly/base rates may be included on timesheet rows or supplied in a separate rate-history file. Multiple rate changes for the same employee are retained.

For each shift AuditHero identifies the latest supplied employee rate effective on or before that shift, then compares it with the SCHADS minimum effective for the selected Award scenario.

A supplied base rate is not treated as complete actual shift pay. Full actual-versus-expected reconciliation requires suitable actual payroll evidence.

## Processing flow

```text
Ordinary CSV/XLSX files
        ↓
AuditHero - Preview Uploaded Files
        ↓
Review detected file roles, fields and audit window
        ↓
AuditHero - Audit Reviewed Uploaded Files
        ↓
Canonical employee / shift / effective-rate evidence
        ↓
Definitive audit where employee facts are known
        +
Selectable SCHADS Award scenarios
        ↓
Gold results and governed metric views
        ↓
AI/BI and Genie
```

Material facts that cannot be established safely are retained as `REQUIRES_REVIEW` or evidence-required findings. Unrelated Award calculations continue.

## Award-oriented AI/BI dashboard

**AuditHero - SCHADS Payroll Compliance** is organized around the audit process rather than raw database tables. The managed dashboard is rebuilt and republished during **AuditHero - Setup** / **AuditHero - Install or Upgrade**.

### Global Audit Filters

The global filter strip is linked across the relevant dashboard datasets rather than only the Award-scenario dataset. Where an equivalent field exists, the filter follows the user across pages.

Global controls include:

- Audit Run;
- Audit / Shift Date;
- Employee;
- SCHADS Stream;
- Level;
- Pay Point;
- Scenario Employment Type;
- Scenario Status;
- Base Rate Status; and
- Definitive Pay Status.

The date control maps to the appropriate date field for each dataset, for example shift date on shift/criteria pages, next-shift date for rest findings, pay-period start for reconciliation, and audit-window start for run history.

Not every global filter is applicable to every page. **Rule Coverage** is rule-library metadata and is intentionally independent of employee/scenario filters. **Readiness** is source-level evidence quality rather than employee shift data, so it uses its own page-level readiness controls.

### Audit Overview

Use this as the starting page for an audit. It summarizes:

- employees and definitive shifts in scope;
- shifts requiring review;
- expected and actual auditable payroll;
- potential underpayment;
- pay-period reconciliation status;
- potential underpayment by employee;
- evidence/review findings by audit area;
- below-minimum-rate findings by employee; and
- a definitive shift attention list.

### Employee Deep Dive

Use the global **Employee** filter and optionally select one employee/pay-period. The page connects:

- definitive shifts and hours;
- expected versus actual auditable pay;
- potential underpayment;
- review shifts;
- expected entitlement over shift dates;
- scenario sensitivity by SCHADS level;
- shift-level calculation detail; and
- pay-period reconciliation.

### Audit Components

Provides a consolidated view of every Award criterion generated for the selected scenario, including:

- criterion/audit area;
- component hours;
- calculated component amounts;
- Award clauses referenced;
- day and shift types;
- evidence/review criteria; and
- calculation evidence.

This is useful when the operator wants to understand *why* an expected entitlement was produced rather than only viewing the final amount.

### Award Explorer

Use the scenario controls for SCHADS stream/classification family, level, pay point, employment type, base-rate status and scenario status.

The same supplied shifts are recalculated under the selected scenario. This supports classification comparison without converting an analytical scenario into a definitive classification decision.

### Classification & Historical Rates

Review each shift against the employee rate effective on that date. The page shows:

- rate effective date and source;
- supplied classification where available;
- selected SCHADS stream, level and pay point;
- supplied employee rate;
- Award minimum base rate;
- rate difference; and
- rate status.

### Penalties & Shiftwork

Inspect ordinary penalties, shiftwork, weekends, public holidays and minimum-engagement components generated by the deterministic engine.

### Overtime

Inspect daily, roster-based and period overtime components, including hours, multipliers, rates, amounts, clauses and calculation evidence.

### Rest & Meal Breaks

Review rest-between-work requirements, actual rest, shortfall, overtime-rest applicability, repriced hours, evidence-backed double-time top-up and meal-break findings.

### Sleepovers, Broken Shifts & Allowances

Review applicable sleepover, broken-shift, minimum-engagement and allowance calculations and evidence requirements.

### Actual vs Expected

This page is reserved for definitive actual-pay reconciliation. It distinguishes calculated expected entitlement from actual payroll evidence and does not treat a supplied base-rate file as complete payroll.

### Evidence Required

Shows facts that could not be established safely from the uploaded files. These findings identify the affected employee/shift and audit area without blocking unrelated calculations.

### Definitive Shift Investigation

Shows the governed shift-level result where employee classification and employment facts are known, including calculation evidence and review flags.

### Audit Runs & Data Quality

Use this page to confirm what AuditHero actually processed and whether the source evidence was sufficiently complete. It includes:

- audit run ID, date window, run type and status;
- employee/timesheet counts;
- actual-pay source;
- underpaid, overpaid and review-period counts;
- persistence/performance detail recorded with the run;
- readiness findings by type and status; and
- detailed source/readiness findings.

### Rules & Audit History

Shows effective-dated SCHADS rule-pack coverage and audit-run history. Rule coverage is deliberately not filtered by employee or Award scenario because it describes the governing rule library itself.

## Stored data

Normalized source evidence is stored in Silver tables such as:

- `schads_payroll.silver.employees`
- `schads_payroll.silver.pay_details`
- `schads_payroll.silver.employment_history`
- `schads_payroll.silver.timesheets`
- `schads_payroll.silver.payroll_earnings`
- `schads_payroll.silver.rostered_shifts`

Gold outputs include:

- `schads_payroll.gold.audit_detail`
- `schads_payroll.gold.rest_break_findings`
- `schads_payroll.gold.pay_period_reconciliation`
- `schads_payroll.gold.award_scenario_detail`
- `schads_payroll.gold.award_criteria_detail`
- `schads_payroll.gold.award_scenario_rest_findings`
- `schads_payroll.gold.audit_event_adjustments`
- `schads_payroll.gold.toil_findings`

Governed semantic views include:

- `schads_payroll.semantic.payroll_compliance`
- `schads_payroll.semantic.audit_detail`
- `schads_payroll.semantic.rest_break_compliance`
- `schads_payroll.semantic.award_scenarios`

Genie queries governed results and semantic measures. SCHADS calculations are performed before results reach the reporting layer.

## Routine file audit

For each later payroll period:

1. replace or upload the source files in `/Volumes/schads_payroll/bronze/landing/import/raw`;
2. run **AuditHero - Preview Uploaded Files** with the required audit dates;
3. review the preview and prepared date window;
4. run **AuditHero - Audit Reviewed Uploaded Files** with the same dates; and
5. review AI/BI, Genie and any evidence-required findings.

When explicit audit dates are supplied, AuditHero processes that requested activity window. Effective-dated history may retain the latest prior governing row as reference context, but activity outside the selected window is not audited.

## Advanced source mapping

Use source mapping only for exports that automatic intake cannot identify reliably:

- **AuditHero - Build Source Mapping Workbook (Advanced)**
- **AuditHero - Convert Source Files (Advanced)**
- **AuditHero - Convert Mapped Files and Run Audit (Advanced)**
- **AuditHero - File Readiness (Advanced)**
- **AuditHero - Audit Canonical CSV Excel (Advanced)**

## Employment Hero API

After Databricks Secrets are configured:

1. run **AuditHero - Employment Hero Connection Test (Optional API)**;
2. run **AuditHero - API Audit Readiness (Optional API)**;
3. use **AuditHero - Monthly Payroll Audit (Optional API)** for recurring audits; or
4. use **AuditHero - Historical SCHADS Audit (Optional API)** for a selected historical range.

API and uploaded-file workflows use the same deterministic calculation and governed result layers.

## Upgrade

Open `/Shared/AuditHero/admin/AuditHero - Install or Upgrade` and choose **Run all**.

Upgrade migrates managed Gold schemas, refreshes the effective-dated rule library, updates Jobs, rebuilds and republishes the Award-oriented dashboard with cross-dataset global filters and enhanced audit pages, and refreshes Genie.

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
