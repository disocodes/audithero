# Importing and mapping CSV / Excel files

AuditHero can audit source exports that do not already use its canonical field names. The source-mapping workflow converts payroll, HR, roster and timekeeping exports into stable AuditHero datasets before File Readiness and SCHADS calculation.

Source mapping is independent of the SCHADS calculation engine. Changes to a source system or export layout are handled by updating the mapping while the Award calculation rules remain unchanged.

## Standard workflow

```text
Raw source exports
      ↓
Build Source Mapping Workbook
      ↓
source_mapping_draft.xlsx
      ↓
review and approve
      ↓
source_mapping.xlsx
      ↓
Convert Mapped Files and Run Audit
      ↓
canonical files
      ↓
File Readiness
      ↓
SCHADS audit
```

## Raw source locations

### Microsoft Fabric

Upload files to:

`/lakehouse/default/Files/import/raw`

### Databricks

Upload files to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

CSV and XLSX files can be used together. Excel workbooks can contain multiple sheets.

Keep the original exports unchanged. Source file names and sheet names can be referenced by the mapping workbook.

## Build the mapping workbook

Run **AuditHero - Build Source Mapping Workbook**.

AuditHero scans each supported source file/sheet, samples its headings and proposes matches to canonical datasets such as:

- employees;
- pay details / classifications;
- employment history;
- timesheets;
- rostered shifts;
- payroll earnings;
- public holidays; and
- controlled evidence datasets where configured.

The generated `source_mapping_draft.xlsx` is a proposal and must be reviewed before conversion.

## `field_mapping` sheet

Each enabled mapping row identifies the AuditHero dataset/field and the corresponding source location.

Example:

| Dataset | AuditHero field | Source file | Source sheet | Source field |
|---|---|---|---|---|
| employees | employee_id | employees.xlsx | Employees | Employee Number |
| employees | employee_name | employees.xlsx | Employees | Full Name |
| timesheets | start_datetime | timesheets.xlsx | Timesheets | Clock In |
| timesheets | end_datetime | timesheets.xlsx | Timesheets | Clock Out |
| payroll_earnings | amount | payroll.xlsx | Earnings | Gross Amount |

Review all required identifiers, dates, employment types, classification values, hours and amounts before approving the mapping.

## Supported mapping operations

The converter supports controlled field transformations such as:

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

Value mappings can also be used for known work types, service groups and other controlled source terminology.

## Classifications

Classification mapping is a payroll-compliance control. Do not map an employee to a SCHADS classification only because a job title appears similar.

The mapping must reflect the applicable classification evidence for the audit period. Historical classification changes should be supplied as effective-dated evidence where required.

## Pay categories

Payroll earnings must be classified for reconciliation. Typical treatment values are:

- `AUDITABLE_WORK` — included in actual auditable pay;
- `ALLOWANCE` — treated as a separately controlled allowance where supported; and
- `EXCLUDE` — excluded from the auditable-pay comparator.

Unmapped pay categories can prevent a reliable actual-versus-expected conclusion.

## Work locations and public holidays

Location data should provide the state used for public-holiday analysis. Where a local public holiday applies, configure a `holiday_location_key` that identifies the relevant local area.

Do not treat a local public holiday as statewide unless that is supported by the source evidence.

## Separate date and time fields

If an export provides dates and times in separate columns, configure the mapping to combine them into the canonical datetime field.

For example:

```text
Shift Date + Start Time → start_datetime
Shift Date + End Time   → end_datetime
```

Review overnight shifts to confirm the end date is represented correctly.

## Multiple files and sheets

A canonical dataset can be sourced from a specific CSV file or Excel sheet. If data is split across source files, use the configured mapping/join capabilities only where a stable source key is available.

Employee identifiers are the preferred key for linking employee, employment-history, pay-detail, timesheet and payroll records.

## Approve the mapping

After review:

1. save the workbook as `source_mapping.xlsx`;
2. upload it to the platform import folder; and
3. run **AuditHero - Convert Mapped Files and Run Audit**.

Use **AuditHero - Convert Source Files** when conversion and File Readiness need to be checked without starting the payroll audit.

## Conversion outputs

The converter writes canonical CSV files and `audithero_input.xlsx` to the platform canonical input folder. It also writes conversion information such as `mapping_used.json` and `conversion_report.csv` where supported.

The conversion report should be reviewed for row counts, blank required fields and unexpected source omissions.

## File Readiness

Successful field conversion does not by itself confirm that the data is audit-ready. File Readiness checks the resulting canonical data for required datasets, columns, classifications, pay-period evidence and controlled historical evidence.

Blocking findings must be resolved before the audit proceeds.

## Reusing a mapping

An approved mapping can be reused for later exports from the same stable source layout. Re-run the mapping review when the source system, report template, sheet name, column name, value coding or file structure changes.

Keep approved mapping versions with the payroll/audit evidence for controlled historical work.
