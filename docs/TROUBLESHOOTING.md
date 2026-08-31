# AuditHero troubleshooting

Start with the message shown by the installer notebook, job or pipeline. AuditHero is designed to stop early when installation, mapping or audit evidence is incomplete.

## Installer notebook cannot create workspace items

Confirm that the user running the installer has permission to create/manage the required items in the target workspace.

### Microsoft Fabric

The installer needs permission to create/manage the AuditHero Lakehouse, Environment, notebooks, Data Factory pipelines, semantic model and Power BI report in the current workspace.

### Databricks

The installer needs permission to create Jobs and the configured Unity Catalog objects. It also needs access to a SQL warehouse for AI/BI.

## Databricks installer says no SQL warehouse is available

Leave `sql_warehouse_id` blank to let AuditHero select an available warehouse. If there are no warehouses and the installer cannot create one because of permissions, create/select a SQL warehouse in the UI, paste its ID into `sql_warehouse_id`, and rerun the installer.

## Databricks Setup job has no usable compute

The installer defaults to serverless Jobs. If serverless Jobs are disabled in the workspace, set `existing_cluster_id` in the installer notebook to a compatible existing cluster ID and rerun.

## Fabric installer cannot obtain a Fabric token

Run the installer as a user with access to the target workspace. The notebook uses the current Fabric notebook identity through `notebookutils.credentials.getToken("pbi")`; it does not require a manually pasted Fabric token.

## Installer fails during Setup or Self Test

Do not continue to production payroll data. Correct the installation/runtime error and rerun the installer. The installer is safe to rerun and updates existing AuditHero items.

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

## Uninstall completed but payroll data is still present

This is the default safe behavior. The uninstaller removes AuditHero application resources but preserves the Lakehouse/catalog unless permanent deletion is explicitly confirmed.

To remove payroll/audit data permanently, rerun the uninstaller with:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

Only use full deletion after the required records have been retained or backed up.
