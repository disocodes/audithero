# Manual CSV / Excel import

AuditHero does **not** require Employment Hero API credentials. A complete audit can run from uploaded CSV/XLSX data in either Microsoft Fabric or Databricks.

## Simplest option: one workbook

Generate a blank workbook:

```bash
pip install -e .
python tools/build_input_workbook.py --output audithero_input.xlsx
```

Populate the workbook and upload it unchanged as `audithero_input.xlsx`.

## Core sheets

### `employees` — required

Minimum:

```text
employee_id
employee_name
```

Recommended:

```text
employment_type_current
state
work_group
```

### `pay_details` — required

```text
employee_id
effective_from
classification_code
```

`classification_code` is the canonical AuditHero SCHADS code, for example `SACS-L2-P3`.

Additional descriptive columns may be retained.

### `employment_history` — required

```text
employee_id
start_date
employment_type
```

Recommended:

```text
end_date
contract_type
title
```

Historical employment type is required because overtime/minimum-engagement logic differs by full-time, part-time and casual status.

### `timesheets` — required

Minimum:

```text
timesheet_id
employee_id
start_datetime
end_datetime
```

Recommended:

```text
unpaid_break_minutes
work_group
location_state
holiday_location_key
work_type_name
is_sleepover
sleepover_active_minutes
sleepover_12h_written_agreement
pay_period_start
pay_period_end
```

`pay_period_start` is particularly important around annual Award changes because new rates commonly apply from the first full pay period commencing on or after the operative date.

## Pay-period helper

If pay-period dates are not repeated on each timesheet, supply the optional `pay_runs` sheet:

```text
pay_run_id
pay_period_start
pay_period_end
status
```

AuditHero will assign a pay period to a shift when exactly one supplied pay run contains that shift date. If multiple pay runs overlap, AuditHero does not guess.

## Rostered shifts — recommended

`rostered_shifts` materially improves full-time overtime testing:

```text
rostered_shift_id
employee_id
rostered_start_datetime
rostered_end_datetime
rostered_break_minutes
```

Without usable roster evidence, full-time overtime questions can be sent to `REQUIRES_REVIEW`.

## Actual payroll earnings — optional

`payroll_earnings` enables under/over-payment reconciliation:

```text
employee_id
pay_period_start
pay_period_end
pay_category
amount
```

Recommended additional fields:

```text
payroll_line_id
pay_run_id
timesheet_id
earning_date
pay_category_id
hours
rate
```

If `payroll_earnings` is absent, AuditHero still calculates expected Award entitlements but reports an entitlement-only/actual-pay-unavailable result instead of claiming an underpayment or overpayment.

## Pay-category treatment

If actual earnings are supplied, add `pay_category_mapping`:

```text
pay_category_id
pay_category
audit_treatment
```

Allowed treatments:

```text
AUDITABLE_WORK
ALLOWANCE
EXCLUDE
```

This prevents unrelated earnings such as leave, reimbursements or bonuses from masking a worked-time underpayment.

## Historical instrument coverage

For a remediation audit add `industrial_instrument_history`:

```text
employee_id
effective_from
effective_to
instrument_type
instrument_name
award_code
document_reference
```

Typical instrument types are:

```text
AWARD
ENTERPRISE_AGREEMENT
IFA
```

This is a critical audit control: a SCHADS-looking classification is not proof that MA000100 governed the employee for the whole historical period.

## Part-time written patterns

Where part-time employees exist, use `part_time_patterns`:

```text
employee_id
effective_from
effective_to
weekday
start_time
end_time
guaranteed_hours
agreement_reference
```

and, where applicable, `part_time_variations`:

```text
employee_id
shift_date
start_time
end_time
agreement_reference
```

## Other evidence sheets

The workbook can also contain:

- `public_holiday_overrides`
- `overtime_rest_controls`
- `meal_break_events`
- `supplemental_events`
- `toil_register`

These use the same columns as the version-controlled examples under `config/`.

Blank optional sheets are acceptable when the event/control is not applicable.

## Separate files instead of one workbook

You may use separate CSV/XLSX files with the same names as the sheets:

```text
employees.csv
pay_details.xlsx
employment_history.csv
timesheets.xlsx
rostered_shifts.csv
payroll_earnings.csv
industrial_instrument_history.xlsx
...
```

CSV and XLSX can be mixed in the same input folder.

## Microsoft Fabric

Upload to:

```text
AuditHero_Lakehouse / Files / input /
```

Run:

```text
AuditHero - Uploaded Files Audit Pipeline
```

The pipeline validates the upload before calculation and then refreshes the Direct Lake/Power BI layer.

## Databricks

Default upload location:

```text
/Volumes/schads_payroll/bronze/landing/input
```

Run:

```bash
databricks bundle run manual_file_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30
```

The Databricks job also runs file readiness before calculation and refreshes the AI/BI dashboard after success.

## Recommended approach

Use file mode first even if you ultimately want API automation:

1. export one known payroll period;
2. populate the workbook;
3. run file readiness;
4. compare representative calculations with payroll manually;
5. resolve mappings/evidence;
6. run the wider historical audit;
7. only then enable API ingestion and recurring unattended jobs.
