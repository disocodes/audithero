# AuditHero administration

This guide covers tasks performed by platform/payroll-system administrators rather than day-to-day audit operators.

## Roles and access

Separate responsibilities where practical:

- **Platform administrator:** installation, workspace permissions, environments/jobs/pipelines and upgrades.
- **Payroll data administrator:** source mappings, pay-category treatment and controlled evidence registers.
- **Audit operator/reviewer:** runs audits and reviews findings.

Payroll data is sensitive. Apply least-privilege access to Lakehouse/Volumes, output tables and dashboards.

## Installation and upgrades

Use the platform installer notebook as the normal installation and upgrade method:

- Fabric: `installers/Fabric_Install_AuditHero.py`
- Databricks: `installers/Databricks_Install_AuditHero.py`

The installer creates/updates the platform resources and runs Setup and Self Test automatically. To upgrade, change the installer `release_ref` to the approved AuditHero version and run the notebook again.

After an upgrade, validate one known payroll period before resuming production or recurring audits.

## Removing AuditHero

Use the matching uninstaller notebook:

- Fabric: `installers/Fabric_Uninstall_AuditHero.py`
- Databricks: `installers/Databricks_Uninstall_AuditHero.py`

Normal uninstall removes AuditHero application resources and preserves payroll/audit storage by default.

Permanent data deletion requires both:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

Before permanent deletion, follow the organisation's payroll-record retention and backup requirements.

## Source mapping governance

Treat `source_mapping.xlsx` as controlled configuration. It determines how source evidence is interpreted before the SCHADS engine runs.

When a source export changes:

1. upload a sample of the new layout;
2. generate/review a new mapping draft;
3. version the approved mapping;
4. convert a known period;
5. compare the conversion report; and
6. manually validate representative audit results.

Do not modify Award calculation code to compensate for a source-system column change.

## Rule-library updates

The authoritative AuditHero rule packs are under `rules/MA000100/`.

When a new approved rate/condition version is added:

1. add a new effective-dated pack rather than editing historical values in place;
2. retain source publisher/reference metadata;
3. validate the manifest;
4. add/update regression cases;
5. install the version in a non-production workspace where required;
6. run Self Test and a known payroll period; and
7. promote only after review.

## Employment Hero API (optional)

### Fabric

Store API secrets in Azure Key Vault. The notebooks retrieve them at runtime; do not place secret values in Git, notebook parameters or Power BI.

### Databricks

Use Databricks Secrets for API credentials. Uploaded-file workflows do not require them.

API connectivity is an ingestion option. It does not replace controlled evidence that cannot be reliably established from the source API.

## Schedules

Recurring payroll audits should be disabled/paused by default. Enable a schedule only after the relevant input path, mapping and known-period validation are stable.

If file mode is used for recurring audits, establish an operational process that replaces/uploads the current source exports before the scheduled conversion/audit run.

## Retention and audit trail

Set retention according to the organisation's payroll/legal requirements. Retain enough evidence to explain:

- source files used;
- mapping version;
- rule-library version;
- AuditHero release/version;
- audit date range;
- run identifier/time;
- readiness/review findings; and
- subsequent corrections.

Do not commit real payroll exports, API secrets or controlled employee evidence to the public/source-code repository.