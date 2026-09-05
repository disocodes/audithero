# AuditHero operator templates

## Public holiday overrides

Use `public_holiday_overrides_template.csv` when you need to supply a one-off, irregular, regional or local public holiday that is not covered by AuditHero's automatic Australian statewide holiday calendar.

For Databricks, **AuditHero - Preview Uploaded Files** also creates the controlled Excel version automatically at:

```text
/Volumes/<catalog>/bronze/landing/templates/public_holiday_overrides_template.xlsx
```

The Excel template contains dropdowns for:

- `state`: `WA`, `NSW`, `VIC`, `QLD`, `SA`, `TAS`, `ACT`, `NT`
- `holiday_scope`: `STATEWIDE`, `LOCAL`
- `source`: `manual_override`, `government_notice`, `gazette`, `employer_calendar`, `other_evidence`

Enter `holiday_date` in Australian day-first format such as `15-08-2025`. Enter `holiday_name` as normal text. For a `LOCAL` holiday, enter a stable `holiday_location_key`; that same key must be present on the affected timesheet rows.

### You can also upload your own holiday file

You do not have to use the AuditHero template. The normal Preview workflow now detects ordinary CSV/XLSX holiday files when they contain recognisable fields for:

- state/territory
- holiday date
- holiday name

and the file/sheet or column headings clearly identify the content as public-holiday information. Common headings such as `State`, `Holiday Date`, `Public Holiday Date`, `Holiday Name`, `Location`, `Scope`, and `Source` are mapped automatically.

Preview converts detected rows into the canonical `public_holiday_overrides` dataset and shows that role in the interpretation output. Invalid dates, missing/unsupported states, invalid scopes, or a `LOCAL` row without a location key fail closed instead of being silently ignored.

Normal operator flow:

```text
upload holiday file with other source files
        ↓
AuditHero - Preview Uploaded Files
        ↓
confirm detected role = public_holiday_overrides
        ↓
AuditHero - Audit Reviewed Uploaded Files
```

Normal statewide Australian public holidays are still generated automatically; this template is only for exceptions and special/local declarations.
