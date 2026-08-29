# Audit data requirements

AuditHero separates **core payroll evidence** from additional evidence needed for specific SCHADS conditions.

## Minimum datasets for entitlement calculation

### employees — required

Minimum fields:

- `employee_id`
- `employee_name`

Useful fields include current employment type, state and work group.

### pay_details — required

Minimum:

- `employee_id`
- `effective_from`
- `classification_code`

`classification_code` must resolve to a code loaded in the AuditHero rule library, such as a supported SACS or Home Care disability-care classification.

### employment_history — required

Minimum:

- `employee_id`
- `start_date`
- `employment_type`

Historical employment type matters because full-time, part-time and casual calculations are not interchangeable.

### timesheets — required

Minimum:

- `timesheet_id`
- `employee_id`
- `start_datetime`
- `end_datetime`

Recommended fields include unpaid breaks, work group, state/local holiday location, work type, sleepover facts and pay-period dates.

## Strongly recommended datasets

### rostered_shifts

Roster evidence improves full-time overtime analysis and matching of worked time to rostered ordinary hours. If required roster evidence is not available, AuditHero may mark the relevant overtime issue for review rather than infer it.

### pay_runs

Pay-run start/end dates help assign each shift to the correct pay period. This is particularly important around effective-dated Award changes and first-full-pay-period rules.

### payroll_earnings

Actual earnings are needed to produce reliable `UNDERPAID`, `OVERPAID` and `COMPLIANT` reconciliation. Without them AuditHero can calculate expected entitlements but will normally report actual pay as unavailable.

## Historical coverage evidence

### industrial_instrument_history

For historical remediation work, this is a key control. A payroll classification label alone does not prove that SCHADS applied to the employee for the whole audit period.

Record effective dates and whether the employee was covered by the Award, an enterprise agreement, an IFA or another relevant arrangement. AuditHero fails closed where instrument coverage cannot be established.

### part_time_patterns

Required where part-time employment exists and the relevant rule depends on the written agreed pattern/guaranteed hours. Keep effective dates and the agreement reference.

### part_time_variations

Use this for documented variations to an agreed part-time pattern.

## Conditional evidence

The following datasets are used when the facts occurred in your workforce:

- `public_holiday_overrides` — local/substituted holidays not covered by the standard state holiday feed;
- `overtime_rest_controls` — evidence relevant to return to work before the applicable rest period;
- `meal_break_events` — worked-through/delayed/client meal events;
- `supplemental_events` — on-call, recall, remote work, higher duties and other supported event types;
- `toil_register` — written TOIL agreements and subsequent time off/payment facts.

A conditional dataset can be empty when the event genuinely did not occur. Do not invent rows just to satisfy a template.

## Pay-category treatment

When payroll earnings are supplied, each relevant source pay category needs an audit treatment. This prevents non-auditable or unrelated payments from being silently included in actual auditable pay.

Review the pay-category mapping with payroll staff before relying on reconciliation totals.

## Dates and identifiers

Use stable employee/timesheet identifiers across datasets. Prefer ISO dates (`YYYY-MM-DD`) and unambiguous datetimes. The mapping pipeline can convert basic source formats, but ambiguous dates should be resolved at the source/mapping stage.

## Data quality principle

AuditHero distinguishes between:

- **missing data that prevents a reliable conclusion** — usually blocking or `REQUIRES_REVIEW`; and
- **optional data for conditions that did not occur** — may legitimately be absent.

The File Readiness workflow displays these differences before the audit runs.
