# AuditHero troubleshooting

Start with the message shown by the job/pipeline. AuditHero tries to fail early with a data/mapping explanation rather than continue to an unreliable payroll result.

## No files found in the mapping job

Check that CSV/XLSX files were uploaded to the configured raw folder.

- Fabric default: `Files/import/raw`
- Databricks default: `/Volumes/<catalog>/bronze/landing/import/raw`

Temporary Excel files beginning with `~$` are ignored.

## A source file/sheet was not detected correctly

Open `source_mapping_draft.xlsx` and change `source_file` and `source_sheet` manually. Auto-detection is only a starting suggestion.

## Conversion says a required field is not mapped

Open `field_mapping`, find the row marked `required = TRUE`, and provide one of:

- `source_field`;
- `coalesce_fields`;
- `concat_fields`;
- date/time source fields; or
- a justified constant.

Do not map a convenient but semantically different source column just to make the error disappear.

## Dates look wrong

Prefer unambiguous source dates. Configure `data_type` appropriately and, where relevant, use separate date/time fields. Inspect canonical CSV output before auditing.

## Employee joins are missing

Check that `employee_id` has the same value/format across employees, employment history, pay details, timesheets and payroll earnings. A mapping that converts one identifier to a number but another to a padded string can break joins.

## File Readiness blocks industrial instrument history

Historical remediation requires evidence of Award/EA/IFA coverage. Add the `industrial_instrument_history` sheet/file with effective dates and references rather than assuming the current Award applied historically.

## File Readiness blocks part-time patterns

Part-time employees were detected. Supply effective-dated written pattern/guaranteed-hours evidence (and variations where relevant).

## Payroll earnings are present but reconciliation is unavailable

Check `pay_category_mapping`. Each relevant payroll category needs a treatment so AuditHero can calculate actual auditable pay.

## Many results are REQUIRES_REVIEW

This usually indicates missing evidence rather than a calculation crash. Review the flags/evidence fields, then supply the facts AuditHero says are ambiguous (for example roster match, pay period, agreement or instrument coverage).

## Power BI / AI/BI has no current data

Confirm that the audit itself completed successfully. BI-facing snapshots are intended to update only after a successful run so a failed audit does not replace the previous valid report.

## Optional API jobs fail

Uploaded-file audits can still operate. For API mode, run the platform's Employment Hero Connection Test first and verify secret access/tenant identifiers before troubleshooting the calculation engine.

## Platform Self Test fails

Do not continue to payroll data. Treat Self Test failure as an installation/version issue and have the platform administrator review the failed assertion and environment/package versions.
