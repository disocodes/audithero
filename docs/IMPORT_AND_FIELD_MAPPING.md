# Importing and mapping CSV/Excel files

AuditHero does not require payroll, HR, rostering or timekeeping exports to use predefined column names. The source-mapping workflow converts organisation-specific CSV/Excel exports into the canonical datasets used by the audit engine.

This mapping layer is deliberately separate from the SCHADS calculation engine. Changing payroll systems should normally mean changing the source mapping, not changing Award calculation code.

## The operator workflow

For most organisations the process is:

1. upload the original source exports;
2. run **AuditHero - Build Source Mapping Workbook**;
3. review the suggested mapping in Excel;
4. save the approved workbook as `source_mapping.xlsx`; and
5. run **AuditHero - Convert Mapped Files and Run Audit**.

After the mapping has been approved once, steps 2-4 normally only need to be repeated when a source system/export layout changes.

## When you need mapping

Use the mapping workflow when source files contain fields such as:

- `Employee Number` instead of `employee_id`;
- `Clock In` instead of `start_datetime`;
- first and last name in separate columns;
- shift date and start/end time in separate columns;
- employment values such as `Permanent PT` instead of `PART_TIME`; or
- payroll categories/amount fields with system-specific names.

You do **not** need mapping when the source already uses `audithero_input.xlsx` or the canonical AuditHero CSV layout.

## Standard folders

### Microsoft Fabric

- raw exports: `AuditHero_Lakehouse / Files / import / raw`
- generated draft: `Files/import/source_mapping_draft.xlsx`
- approved mapping: `Files/import/source_mapping.xlsx`
- converted canonical files: `Files/input`

### Databricks

- raw exports: `/Volumes/<catalog>/bronze/landing/import/raw`
- generated draft: `/Volumes/<catalog>/bronze/landing/import/source_mapping_draft.xlsx`
- approved mapping: `/Volumes/<catalog>/bronze/landing/import/source_mapping.xlsx`
- converted canonical files: `/Volumes/<catalog>/bronze/landing/input`

## Step 1 — upload the original exports

Upload the files as they came from the source systems. CSV and Excel files may be mixed, and an Excel workbook may contain multiple sheets.

Do not manually rename or rearrange columns merely to make AuditHero accept the file. Keeping the original export intact makes the evidence trail easier to understand and reproduce.

AuditHero deliberately restricts mapping references to files under the configured raw source folder.

## Step 2 — build a draft mapping workbook

Run **AuditHero - Build Source Mapping Workbook** from the platform UI.

The job/pipeline scans:

- source filenames;
- Excel sheet names;
- column headings; and
- a small sample of rows needed to understand the structure.

It then creates `source_mapping_draft.xlsx` with suggested dataset and field matches.

Suggestions are not approvals. Required fields should always be checked by someone who understands the source exports.

## Step 3 — edit the mapping workbook

The workbook is intended to be edited in Excel by an administrator or payroll data owner.

### `README` sheet

Explains the supported mapping operations and how the workbook is used.

### `field_mapping` sheet

Each row defines how one AuditHero target field is produced. Important columns include:

- `dataset` — target dataset, such as `employees`, `timesheets` or `payroll_earnings`;
- `enabled` — whether AuditHero should build the dataset;
- `source_file` — source file relative to the raw folder;
- `source_sheet` — Excel sheet name; blank for CSV;
- `target_field` — AuditHero canonical field;
- `required` — whether the field is required for that dataset;
- `source_field` — direct source-column match;
- `coalesce_fields` — semicolon-separated alternatives; first non-blank value wins;
- `concat_fields` — semicolon-separated fields to join;
- `concat_separator` — text inserted between joined fields;
- `date_source` and `time_source` — combine separate date and time fields;
- `constant` — fixed value used for every row;
- `default` — value used when the mapped value is blank;
- `data_type` — optional conversion such as string, number, integer, date, datetime or boolean; and
- `confidence` — informational confidence of the original suggestion.

### `value_mapping` sheet

Use this sheet when source values themselves need translation.

Example:

| dataset | target_field | source_value | target_value |
|---|---|---|---|
| employees | employment_type_current | Permanent Full Time | FULL_TIME |
| employees | employment_type_current | Permanent Part Time | PART_TIME |
| employees | employment_type_current | Casual Employee | CASUAL |

## Common mapping examples

### Direct field

Source:

`Employee Number`

Target:

`employee_id`

Set `source_field = Employee Number`.

### Combine first and last name

Set:

`concat_fields = First Name;Last Name`

and set `concat_separator` to a single space.

### Combine a shift date and time

For target `start_datetime`:

- `date_source = Shift Date`
- `time_source = Start Time`
- `data_type = datetime`

Repeat for `end_datetime`.

### Use whichever employee identifier is populated

If one export contains both `Employee Number` and `Payroll ID` but only one is populated on some rows:

`coalesce_fields = Employee Number;Payroll ID`

### Add a constant

If all rows in a source file belong to one known work stream, set for example:

`constant = DISABILITY_SERVICES`

for the target `work_group`.

### Convert values

Use `value_mapping` rather than editing the raw source file. Examples:

- `Permanent PT` → `PART_TIME`
- `Y` → `true`
- `Western Australia` → `WA`

### Boolean fields

Set `data_type = boolean`. AuditHero accepts common values such as true/false, yes/no and 1/0.

## Step 4 — approve the mapping

Save the reviewed mapping workbook as:

`source_mapping.xlsx`

Treat this file as controlled configuration. It determines how source evidence enters the audit and should therefore be retained with the payroll-audit records for the period/version in which it was used.

Do not accept a suggested mapping solely because its confidence score is high.

## Step 5 — convert and audit

For normal operation, run:

**AuditHero - Convert Mapped Files and Run Audit**

The combined pipeline/job:

1. loads the approved mapping;
2. converts the raw exports into canonical AuditHero datasets;
3. creates individual canonical CSV files;
4. creates `audithero_input.xlsx`;
5. writes `mapping_used.json` and `conversion_report.csv`;
6. runs File Readiness checks;
7. stops if blocking data/evidence problems remain;
8. runs the SCHADS audit if readiness passes; and
9. refreshes Power BI or Databricks AI/BI after a successful audit.

If you only want to test the mapping/conversion without running payroll calculations, run:

**AuditHero - Convert Source Files**

## Understanding the conversion report

`conversion_report.csv` shows, by dataset/field where available:

- source selected;
- mapping rule used;
- rows converted;
- blanks in required fields; and
- conversion/readiness issues.

Conversion success means the files were structurally converted. It does **not** by itself prove the payroll evidence is sufficient for a reliable Award result; File Readiness performs that separate check.

## File Readiness checks

Typical blocking findings include:

- a required canonical dataset was not created;
- required columns are missing;
- canonical classification codes are blank;
- historical industrial-instrument evidence is missing; or
- part-time employment exists without the required effective-dated part-time pattern evidence.

Correct either the source data or the mapping and rerun the pipeline.

## Payroll category mapping

If actual payroll earnings are supplied, AuditHero must know which earnings lines belong in auditable pay. Common treatment values are:

- `AUDITABLE_WORK`
- `ALLOWANCE`
- `EXCLUDE`

The mapping layer can build the canonical `pay_category_mapping` dataset from a payroll export or separate mapping sheet.

## JSON mapping option for administrators

Excel is the preferred human-editable mapping interface. Administrators who manage mappings in source control can use the equivalent JSON structure demonstrated in `config/source_mapping.example.json`.

Both formats describe the same source-to-canonical transformation and use the same safe conversion operations. The mapper does not execute arbitrary Python or formulas supplied by the mapping file.

## When a source system changes

When an organisation changes payroll/timekeeping systems or the export layout changes:

1. retain the old approved mapping with the old audit records;
2. upload a representative new export;
3. build a new mapping draft;
4. approve a new `source_mapping.xlsx` version;
5. convert and audit one known payroll period; and
6. only then use the new mapping for normal/historical runs.

This keeps source-system changes separate from the Award rules and calculation engine.
