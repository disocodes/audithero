# Supplemental entitlement events

Some SCHADS entitlements cannot be safely inferred from one normal timesheet. AuditHero therefore accepts an optional controlled CSV at:

`/Volumes/<catalog>/bronze/landing/supplemental_events.csv`

Start from `config/supplemental_events.example.csv`.

Supported event types are `ON_CALL`, `RECALL_WORKPLACE`, `SLEEPOVER_ACTIVE`, `REMOTE_WORK`, `CARE_24H`, `BROKEN_SHIFT_ALLOWANCE`, and `HIGHER_DUTIES`.

## Why this is separate

A payroll audit should not invent facts. For example, a 30-minute timesheet does not prove it was a recall to the workplace, and two separated work periods do not by themselves prove a qualifying broken shift. The event file is the controlled evidence layer for facts supplied by Payroll/HR or another verified source.

## Rules currently implemented

- **Recall to workplace:** overtime rate with a two-hour minimum.
- **Active work during sleepover:** overtime with a one-hour minimum.
- **On-call:** applicable weekday or other-day allowance.
- **Remote work:** minimum engagement depends on whether the employee was on-call and the time of the work; longer/complex overtime overlaps remain review findings.
- **Broken shift:** one/two-break allowance can be calculated where the break count and two-break agreement are supplied; period minimums and work beyond the 12-hour span are explicitly checked/reviewed.
- **Higher duties:** Home Care and other employee thresholds are treated separately.
- **24-hour care:** the 155% base component can be calculated only for a supported Home Care classification; the event remains review-controlled because 24-hour-care pay replaces ordinary shift treatment rather than simply adding to it.

Only supplemental events with status `CALCULATED` are added to the expected-pay reconciliation. `REQUIRES_REVIEW` events remain visible in `gold.audit_event_adjustments` but do not inflate a remediation number.
