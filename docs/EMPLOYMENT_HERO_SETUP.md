# Employment Hero setup

## HR API

Create an OAuth application in Employment Hero and grant the scopes required for your organisation's data. AuditHero uses organisation, employee, employee pay-detail, employee employment-history, timesheet-entry, award/classification, work-type, work-location and pay-category endpoints.

Timesheets are pulled with the documented wildcard employee identifier `-` for all employees, and long historical ranges are divided into month-sized requests.

`Pay Details` and `Employment History` are important: a current classification or employment type is not enough evidence for a three-year audit.

## OAuth / PKCE

Employment Hero has announced PKCE as mandatory for authorisation flows from **14 September 2026**. Use `tools/eh_oauth_pkce.py` to bootstrap the refresh token. Store the refresh token in Databricks Secrets; do not commit it.

## Payroll API

Actual paid earnings can be pulled from the Employment Hero Payroll / YourPayroll API when available. Store:

```text
EH_PAYROLL_API_KEY
EH_PAYROLL_BUSINESS_ID
```

If unavailable, run with `actual_pay_source=NONE`. AuditHero will calculate expected entitlements but will not claim that a worker was under- or over-paid without actual-pay evidence.

## Why mappings are mandatory

Every tenant can use different classification and earnings-category names. Configure the files in `config/` so arbitrary labels cannot silently change audit conclusions. An unmapped pay category becomes `REQUIRES_REVIEW`.
