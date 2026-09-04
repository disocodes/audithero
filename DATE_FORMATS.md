# AuditHero date formats

AuditHero is designed for Australian payroll auditing. Human-entered and file-based numeric dates therefore use **day-first (DD-MM-YYYY) interpretation**.

## Accepted date formats

The following all represent **2 March 2024**:

- `02-03-2024`
- `02/03/2024`
- `02.03.2024`
- `2 Mar 2024`
- `2024-03-02`

Date/time values may include a time, for example:

- `02-03-2024 09:30`
- `02/03/2024 09:30:00`
- `2024-03-02T09:30:00`

ISO `YYYY-MM-DD` and ISO timestamps remain fully supported for APIs, rule packs, storage and machine-generated data.

## Ambiguous numeric dates

AuditHero never treats an ambiguous human-entered numeric date as month-first.

For example:

- `02-03-2024` means **2 March 2024**, not February 3.
- `04/05/2024` means **4 May 2024**, not April 5.

This policy applies consistently to normal CSV/XLSX intake, canonical files, Advanced Mapping conversion, readiness checks, rule selection, public holidays, historical employment evidence, part-time patterns, payroll periods, supplemental events, TOIL, overtime/rest calculations, Employment Hero historical ranges, and persisted audit windows.

## Invalid dates

AuditHero fails closed on invalid dates rather than guessing. For example, `31-02-2024` is invalid and is surfaced as invalid/review evidence where applicable.

## Job parameters

For Fabric and Databricks audit jobs, operators may enter Australian day-first dates such as `01-07-2024` or ISO dates such as `2024-07-01`. AuditHero normalizes valid audit-window parameters internally to ISO before API requests and persistence.

## Recommended practice

For Australian operator-entered files, `DD-MM-YYYY` or `DD/MM/YYYY` is supported directly. For system-to-system integrations and generated configuration, ISO `YYYY-MM-DD` is recommended because it is intrinsically unambiguous.
