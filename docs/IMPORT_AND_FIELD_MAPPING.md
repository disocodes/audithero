# Importing and mapping CSV / Excel files

AuditHero is designed to accept ordinary payroll, HR, roster and timekeeping CSV/XLSX exports without requiring operators to remodel them first.

The preferred workflow is **preview first, correct only if needed**. Advanced Mapping is an optional correction/context layer; it is not the primary evidence source and is not required when automatic intake is already correct.

## Standard workflow

```text
Upload original CSV/XLSX exports
      ↓
AuditHero automatic intake
      ↓
Preview detected files, roles and fields
      ↓
Interpretation correct?
   ┌───────┴────────┐
  Yes              No / incomplete
   │                    ↓
   │          Generate Advanced Mapping workbook
   │                    ↓
   │          Correct file role / field mapping
   │          Add optional file context
   │                    ↓
   └──────────────┬─────┘
                  ↓
          Canonical conversion
                  ↓
             File Readiness
                  ↓
              SCHADS audit
```

Keep all original source exports unchanged. The Advanced Mapping workbook explains how AuditHero should interpret those files; it does not replace them.

## Raw source locations

### Microsoft Fabric

Upload files to:

`/lakehouse/default/Files/import/raw`

### Databricks

Upload files to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

CSV and XLSX files can be used together. Excel workbooks can contain multiple sheets.

## Automatic preview

AuditHero scans each uploaded file/sheet, samples headings and proposes roles such as:

- employee records;
- pay details / classifications;
- employment history;
- timesheets;
- rostered shifts;
- payroll earnings / actual pay;
- pay runs;
- public holidays; and
- controlled evidence datasets where configured.

The operator should review the preview before running an audit. When the detected role and mapped fields are correct, Advanced Mapping is not required.

## Advanced Mapping workbook

Run **AuditHero - Build Source Mapping Workbook** only when the preview is wrong, incomplete or needs extra context.

The generated `source_mapping_draft.xlsx` contains:

- `preview` — the automatic interpretation that existed when the workbook was generated;
- `file_context` — lets the operator confirm/correct what an uploaded file represents and optionally describe its evidentiary purpose;
- `field_mapping` — source-to-AuditHero field mapping;
- `value_mapping` — controlled source-value translations; and
- `pay_category_treatment` when payroll earning-line detail is available.

Dropdown selections are populated from the uploaded source files and AuditHero's controlled schema wherever practical. Operators should select rather than retype file roles, source headings and mapping controls.

## `file_context` sheet

Use this sheet when AuditHero misunderstood what a file represents or when extra audit context is useful.

Example:

| Source file | Detected role | Selected role | Evidence purpose |
|---|---|---|---|
| payroll.xlsx | CONTEXT_ONLY | payroll_earnings | Final payroll earning lines confirming amounts paid |
| adjustments.xlsx | CONTEXT_ONLY | supplemental_events | Back-pay and manual payroll corrections |
| roster.xlsx | rostered_shifts | rostered_shifts | Planned shifts |

A corrected primary role can be used to tell AuditHero that a file is, for example, the payroll earning source required for actual-pay reconciliation.

This is particularly useful in historical audits where multiple payroll systems or legacy exports are supplied.

## `field_mapping` sheet

Each mapping row identifies the AuditHero dataset/field and the corresponding source location.

Example:

| Dataset | AuditHero field | Source file | Source sheet | Source field |
|---|---|---|---|---|
| employees | employee_id | employees.xlsx | Employees | Employee Number |
| employees | employee_name | employees.xlsx | Employees | Full Name |
| timesheets | start_datetime | timesheets.xlsx | Timesheets | Clock In |
| timesheets | end_datetime | timesheets.xlsx | Timesheets | Clock Out |
| payroll_earnings | amount | payroll.xlsx | Earnings | Gross Amount |

Source-field cells use dropdowns populated from uploaded headings where available, reducing spelling and schema-key errors.

Review all required identifiers, dates, employment types, classification values, hours and amounts before approving a correction.

## Supported mapping operations

The converter supports controlled transformations such as:

- direct source-column copy;
- coalesce from multiple possible source columns;
- concatenate source values;
- combine separate date and time columns;
- constant values;
- defaults;
- value translation; and
- basic data-type conversion.

The mapping workbook does not execute arbitrary Python expressions.

## `value_mapping` sheet

Use `value_mapping` when source values need translation into AuditHero canonical values.

Examples:

| Source value | Canonical value |
|---|---|
| Permanent FT | FULL_TIME |
| Permanent PT | PART_TIME |
| Casual Employee | CASUAL |

## Classifications

Classification mapping is a payroll-compliance control. Do not map an employee to a SCHADS classification only because a job title appears similar.

The mapping must reflect the applicable classification evidence for the audit period. Historical classification changes should be supplied as effective-dated evidence where required. Uncertain classification evidence should result in review rather than an invented classification.

## Pay categories and actual-pay reconciliation

Payroll earnings are supporting evidence that lets AuditHero compare expected remuneration with what was actually paid.

Typical treatment values are:

- `AUDITABLE_WORK` — included in actual auditable pay;
- `ALLOWANCE` — treated as a separately controlled allowance where supported; and
- `EXCLUDE` — excluded from the worked-pay comparator, for example leave or reimbursement items.

A payroll file is useful but not necessarily required to calculate award entitlements. When actual-pay evidence is absent or incomplete, AuditHero can still calculate supported entitlements but must clearly report that actual-versus-expected reconciliation is unavailable or incomplete.

## Supporting and contextual evidence

Additional files can improve audit accuracy and explain what happened without becoming mandatory inputs. Examples include rosters, leave records, payroll adjustments, allowance registers, payment confirmations, employment contracts and classification history.

For example, a main payroll file may appear to show an underpayment while a later adjustment file proves that the difference was subsequently corrected. Correct file context allows AuditHero to include that evidence in reconciliation rather than reporting a misleading outstanding variance.

## Approval and conversion

After correcting the workbook where required:

1. save it as `source_mapping.xlsx`;
2. upload it to the platform import folder; and
3. run **AuditHero - Convert Mapped Files and Run Audit**.

Use **AuditHero - Convert Source Files** when conversion and File Readiness need to be checked without starting the payroll audit.

## Conversion outputs and traceability

The converter writes canonical CSV files and `audithero_input.xlsx` to the canonical input folder. It also writes conversion information such as `mapping_used.json` and `conversion_report.csv` where supported.

The intended evidence chain is:

```text
Original source files
        +
Approved interpretation/correction mapping (when used)
        ↓
Canonical transformed data
        ↓
Audit results and reconciliation
```

This allows a later reviewer to understand both the original evidence and how AuditHero interpreted it.

## File Readiness

Successful field conversion does not by itself confirm that the data is audit-ready. File Readiness checks the resulting canonical data for required datasets, columns, classifications, pay-period evidence and controlled historical evidence.

Blocking findings must be resolved before the relevant audit conclusion proceeds. Optional evidence should improve confidence and reconciliation rather than unnecessarily block the entire audit.

## Reusing a mapping

An approved mapping can be reused for later exports from the same stable source layout. Re-run the preview/mapping review when the source system, report template, sheet name, column name, value coding or file structure changes.

Keep approved mapping versions with the payroll/audit evidence for controlled historical work.
