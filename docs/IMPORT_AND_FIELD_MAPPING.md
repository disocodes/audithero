# Importing and mapping CSV/Excel files

AuditHero does not require your payroll exports to use predefined column names. The source-mapping workflow converts organisation-specific CSV/Excel exports into the canonical datasets used by the audit engine.

## When you need mapping

You need the mapping workflow when your source looks like this:

- `Employee Number` instead of `employee_id`;
- `Clock In` instead of `start_datetime`;
- first and last name in separate columns;
- dates and times in separate columns;
- employment values such as `Permanent PT` rather than `PART_TIME`; or
- payroll categories/amount fields with system-specific names.

You do **not** need mapping if you already use `audithero_input.xlsx` or canonical CSV files.

## Standard folder layout

### Fabric

- raw exports: `Lakehouse / Files / import / raw`
- draft mapping: `Files/import/source_mapping_draft.xlsx`
- approved mapping: `Files/import/source_mapping.xlsx`
- canonical output: `Files/input`

### Databricks

- raw exports: `/Volumes/<catalog>/bronze/landing/import/raw`
- draft mapping: `/Volumes/<catalog>/bronze/landing/import/source_mapping_draft.xlsx`
- approved mapping: `/Volumes/<catalog>/bronze/landing/import/source_mapping.xlsx`
- canonical output: `/Volumes/<catalog>/bronze/landing/input`

## Step 1 — upload raw files

Upload the files as exported from your source systems. You may mix CSV and Excel files and use multiple Excel sheets.

Keep source files under the raw import folder. AuditHero deliberately refuses mappings that point outside the configured source folder.

## Step 2 — build a draft mapping

Run **AuditHero - Build Source Mapping Workbook**.

AuditHero scans file names, Excel sheet names and headers and suggests likely matches. These are suggestions, not approvals. The job writes `source_mapping_draft.xlsx`.

## Step 3 — edit `field_mapping`

The mapping workbook has three sheets:

### README

Instructions and a description of the supported mapping operations.

### field_mapping

Each row maps one AuditHero target field. Important columns are:

- `dataset` — target dataset such as `employees` or `timesheets`;
- `enabled` — whether to create that dataset;
- `source_file` — source file relative to the raw folder;
- `source_sheet` — Excel sheet name (blank for CSV);
- `target_field` — AuditHero canonical field;
- `required` — whether the audit requires the field;
- `source_field` — a direct source-column match;
- `coalesce_fields` — semicolon-separated alternatives; first non-blank value wins;
- `concat_fields` — semicolon-separated fields to join;
- `date_source` / `time_source` — combine separate date/time fields;
- `constant` — one value for every row;
- `data_type` — optional conversion: string, number, integer, date, datetime, boolean;
- `default` — value used if the mapped value is blank; and
- `confidence` — informational confidence of the original suggestion.

### value_mapping

Use this sheet to translate source values without changing the original files.

Example:

| dataset | target_field | source_value | target_value |
|---|---|---|---|
| employees | employment_type_current | Permanent Full Time | FULL_TIME |
| employees | employment_type_current | Permanent Part Time | PART_TIME |
| employees | employment_type_current | Casual Employee | CASUAL |

## Mapping examples

### Direct field

`Employee Number` → `employee_id`

Use `source_field = Employee Number`.

### Join first and last name

Set `concat_fields` to:

`First Name;Last Name`

and separator to a single space.

### Separate shift date and start time

For `start_datetime`:

- `date_source = Shift Date`
- `time_source = Start Time`
- `data_type = datetime`

### Fallback employee identifier

If one export sometimes has `Employee Number` and sometimes `Payroll ID`, set:

`coalesce_fields = Employee Number;Payroll ID`

### Constant work group

If every row belongs to the same service stream, use `constant = DISABILITY_SERVICES`.

### Boolean conversion

Set `data_type = boolean`. AuditHero recognizes common values such as yes/no, true/false and 1/0.

## Step 4 — approve the mapping

Save the reviewed workbook as **`source_mapping.xlsx`** in the import folder. Treat this workbook as controlled configuration because it determines how source evidence enters the audit.

Do not leave an auto-suggested mapping unreviewed simply because confidence is high.

## Step 5 — convert

Run **AuditHero - Convert Source Files**.

The converter performs only documented safe transformations. It does not execute formulas, Python snippets or arbitrary expressions from the workbook.

It creates:

- canonical CSV files;
- `audithero_input.xlsx`;
- `conversion_report.csv`; and
- `mapping_used.json`.

The conversion report shows target field, mapping rule, row count, blank values and readiness status.

## Step 6 — File Readiness

The conversion workflow runs AuditHero's File Readiness checks immediately after conversion. Typical blocking findings include:

- a required canonical dataset was not created;
- required columns are missing;
- classification codes are blank;
- historical industrial-instrument evidence is missing; or
- part-time employees exist but part-time pattern evidence is missing.

Correct the mapping or source data and rerun conversion until blocking findings are resolved.

## Mapping payroll categories

If actual payroll earnings are supplied, AuditHero also needs to know which pay categories belong in auditable pay. The canonical treatment values are normally:

- `AUDITABLE_WORK`
- `ALLOWANCE`
- `EXCLUDE`

The audit loader accepts both the original AuditHero workbook column convention (`pay_category_id`, `pay_category`, `audit_treatment`) and the generic mapper convention (`source_key`, `source_label`, `treatment`).

## Changing source systems

Do not modify the SCHADS engine when a source system changes. Create a new version of `source_mapping.xlsx`, convert the new exports and validate a known payroll period. This keeps source-system transformations separate from Award calculations.
