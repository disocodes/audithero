# Importing and mapping CSV / Excel files

AuditHero accepts ordinary payroll, HR, roster and timekeeping CSV/XLSX exports without requiring operators to remodel them first.

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
   │          Advanced Mapping workbook
   │                    ↓
   │          Correct role / field / values
   │                    ↓
   └──────────────┬─────┘
                  ↓
         reviewed canonical evidence
                  ↓
              SCHADS audit
```

Keep all original source exports unchanged. Mapping describes how AuditHero should interpret evidence; it does not replace the evidence.

## Raw source locations

### Microsoft Fabric

`/lakehouse/default/Files/import/raw`

### Databricks

`/Volumes/schads_payroll/bronze/landing/import/raw`

CSV and XLSX files can be used together. Excel workbooks can contain multiple sheets.

## Automatic preview

Run **AuditHero - Preview Uploaded Files**. The standard preview publishes:

- a table showing each source file/sheet and its detected role(s);
- the source fields recognised in that item;
- canonical prepared files for the recognised evidence;
- `auto_intake_preview.csv`; and
- `auto_intake_manifest.json` containing the prepared audit window and interpretation metadata.

Automatic intake is conservative. It does not assume a work group, employment type, industrial instrument or classification merely because those facts are missing.

A standalone payroll earning source is automatically recognised only when it contains a usable employee ID, pay-period start, pay-period end, pay category and amount.

## Advanced Mapping workbook

Run **AuditHero - Build Source Mapping Workbook (Advanced)** when the automatic interpretation is wrong, incomplete or needs additional context.

The generated `source_mapping_draft.xlsx` contains:

- `preview` — the automatic mapping proposal;
- `file_context` — file/sheet role, primary-source and evidence context controls;
- `field_mapping` — canonical field to source-column mapping;
- `value_mapping` — controlled source-value translations; and
- `pay_category_treatment` — added when payroll earning categories are detected.

Dropdowns are populated from the uploaded file inventory and controlled AuditHero values wherever practical. Use the dropdown selections rather than typing internal schema identifiers.

## `file_context`

The `file_context` sheet controls whether and how an uploaded file/sheet participates in conversion.

Key fields:

- `selected_role` — the canonical dataset represented by the item, or a special role;
- `use_as_primary_source` — marks the item as the primary source for the selected canonical dataset;
- `evidence_purpose` — optional descriptive audit context;
- `period_start` / `period_end` — optional source-document period context;
- `document_status` — optional description such as draft/final/adjustment; and
- `notes` — optional review notes.

Special roles:

- `CONTEXT_ONLY` — retain/document the item as supporting context but do not use it as the canonical source for a dataset;
- `IGNORE` — exclude the item from mapping/conversion.

Only one primary source can be selected for a canonical dataset. Duplicate primary selections are rejected.

Selecting a canonical role changes source selection; it does not by itself create missing field mappings. Required canonical fields must still be mapped in `field_mapping`.

## `field_mapping`

Each row identifies one canonical AuditHero field and the corresponding source location.

Example:

| Dataset | AuditHero field | Source file | Source sheet | Source field |
|---|---|---|---|---|
| employees | employee_id | employees.xlsx | Employees | Employee Number |
| employees | employee_name | employees.xlsx | Employees | Full Name |
| timesheets | start_datetime | timesheets.xlsx | Timesheets | Clock In |
| timesheets | end_datetime | timesheets.xlsx | Timesheets | Clock Out |
| payroll_earnings | amount | payroll.xlsx | Earnings | Gross Amount |

Supported controlled operations include:

- direct source-column copy;
- coalesce across alternative columns;
- concatenation;
- separate date/time combination;
- constants;
- defaults;
- source-value translation; and
- basic data-type conversion.

The mapping workbook does not execute arbitrary Python expressions.

## `value_mapping`

Use value mapping when source codes or labels need an approved canonical translation.

Examples:

| Source value | Canonical value |
|---|---|
| Permanent FT | FULL_TIME |
| Permanent PT | PART_TIME |
| Casual Employee | CASUAL |

Value translation should not be used to invent Award coverage or classification facts that are not supported by evidence.

## Classification controls

Do not map an employee to a SCHADS classification only because a job title appears similar. Classification mapping must reflect the applicable evidence for the audit period. Historical changes should be effective-dated.

When a source label does not explicitly and reliably identify the supported SCHADS stream, level and pay point, use controlled mapping/evidence review rather than inference.

## Payroll earnings and pay-category treatment

Payroll earning evidence supports actual-versus-expected reconciliation. Required earning-line fields are:

- employee ID;
- pay-period start;
- pay-period end;
- pay category; and
- amount.

Approved treatment values are:

- `AUDITABLE_WORK` — included in worked-pay reconciliation;
- `ALLOWANCE` — handled as a controlled allowance category where supported; and
- `EXCLUDE` — excluded from the worked-pay comparator.

Detected payroll earnings without approved pay-category treatment remain evidence but do not enable definitive actual-pay reconciliation.

A missing payroll amount is not interpreted as zero.

## Supplemental and adjustment evidence

Payroll adjustments, back-pay records, allowances and other events affect calculation/reconciliation only when they are mapped into a canonical dataset the audit engine consumes (for example `payroll_earnings` or an applicable controlled supplemental dataset). Describing an item as context alone does not alter calculated pay.

This distinction preserves audit traceability: descriptive context explains the source; canonical mapping determines whether the evidence enters calculation.

## Approval and conversion

After correction:

1. save the approved workbook as `source_mapping.xlsx`;
2. upload it to the platform import location; and
3. run **AuditHero - Convert Mapped Files and Run Audit (Advanced)**.

Use **AuditHero - Convert Source Files (Advanced)** when conversion/readiness should be reviewed without starting calculation.

## Conversion outputs and traceability

Conversion writes canonical CSV files, `audithero_input.xlsx`, `conversion_report.csv` and `mapping_used.json` where supported. The mapping record preserves the approved file-context information as well as dataset mappings.

Evidence chain:

```text
Original source files
        +
Approved mapping/context (when required)
        ↓
Canonical transformed evidence
        ↓
Readiness / audit calculation
        ↓
Run-scoped results and calculation evidence
```

## File Readiness

Successful conversion does not prove audit readiness. Readiness validates required datasets/values, conversions, key relationships, shift intervals, classifications, historical controls and actual-pay controls.

Blocking findings must be resolved for workflows requiring full readiness. Optional actual-pay evidence can remain unavailable while supported entitlement-only analysis proceeds.

## Reusing a mapping

Reuse an approved mapping only while the source report structure and coding remain stable. Re-run preview/mapping review after changes to the source system, report template, sheet, columns, codes or payroll categories.

Keep approved mappings with the relevant audit evidence when performing controlled historical work.
