# Compliance control registers

These files live in `Files/config` in the AuditHero Lakehouse and provide facts that an ordinary timesheet cannot safely prove.

## `industrial_instrument_history.csv`

Effective-dated Award / enterprise agreement / IFA / salary-offset coverage. If the applicable instrument is not SCHADS, AuditHero treats SCHADS as a comparator and prevents a false Award-compliant conclusion.

## `part_time_patterns.csv` and `part_time_variations.csv`

Historical written guaranteed-hour patterns and agreed variations for part-time staff. Current rosters are not accepted as proof of the historical written agreement.

## `overtime_rest_controls.csv`

Evidence for the 10-hour rest-after-overtime control and whether an employer instructed an employee to resume before the required rest expired.

## `meal_break_events.csv`

Worked-through meal breaks, client meals and actual/deducted break evidence.

## `supplemental_events.csv`

On-call, workplace recall, remote work, active work during sleepover, higher duties and other events not represented adequately by the standard timesheet line.

## `toil_register.csv`

Written TOIL agreements, overtime worked, time off taken, payment requests and employment-end facts.

## `public_holiday_overrides.csv`

Verified local/substituted holidays, including `holiday_location_key` so a local holiday cannot leak to every employee in the state.

These registers are audit evidence. Changes should be access-controlled and retained with the payroll audit record.