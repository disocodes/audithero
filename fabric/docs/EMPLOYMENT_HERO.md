# Employment Hero on Fabric

The Fabric edition uses the same Employment Hero clients as Databricks.

## HR data pulled

- employees
- pay-detail/classification history
- employment history
- date-range timesheets
- rostered shifts
- award/classification metadata for readiness
- pay categories, work types and locations for mapping

Large historical timesheet/roster ranges are chunked by month.

## Actual payroll

When the Employment Hero Payroll API is available, AuditHero also pulls pay runs and earnings lines and assigns pay-period boundaries back to timesheets. This is important because Award increases commonly apply from the first full pay period starting on/after an operative date.

If Payroll API access is unavailable, run entitlement-only mode (`actual_pay_source=NONE`). The engine must not label a pay period underpaid/overpaid without actual paid earnings.

## Tenant mappings

After connection/readiness, edit the files in the Lakehouse:

`Files/config/classification_mapping.json`
`Files/config/pay_category_mapping.json`
`Files/config/work_type_mapping.json`
`Files/config/work_location_state_mapping.json`
`Files/config/employee_overrides.json`

Unmapped values are review findings rather than guessed mappings.