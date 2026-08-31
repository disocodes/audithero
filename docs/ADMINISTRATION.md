# AuditHero administration

This guide covers tasks performed by platform/payroll-system administrators rather than day-to-day audit operators.

## Roles and access

Separate responsibilities where practical:

- **Platform administrator:** installation, workspace permissions, environments/jobs/pipelines and upgrades.
- **Payroll data administrator:** source mappings, pay-category treatment and controlled evidence registers.
- **Audit operator/reviewer:** runs audits and reviews findings.

Payroll data is sensitive. Apply least-privilege access to Lakehouse/Volumes, output tables and dashboards.

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

When Fair Work publishes a new rate/condition version:

1. add a new effective-dated pack rather than editing historical values in place;
2. record source publisher/reference metadata;
3. validate the manifest;
4. add/update regression cases;
5. deploy to a non-production target;
6. run Self Test and a known payroll period; and
7. promote only after review.

## Employment Hero API (optional)

### Fabric

Store API secrets in Azure Key Vault. The notebooks retrieve them at runtime; do not place secret values in Git, notebook parameters or Power BI.

### Databricks

Use Databricks Secrets for API credentials. The uploaded-file workflows do not require them.

API connectivity should be treated as an ingestion convenience. It does not replace controlled evidence that is not reliably available from the source API.

## Schedules

Recurring payroll audits should be disabled/paused by default. Enable a schedule only after the relevant input path, mapping and known-period validation are stable.

If file mode is used for recurring audits, establish an operational process that replaces/uploads the current source exports before the scheduled conversion/audit job runs.

## Retention and audit trail

Set retention according to your organisation's payroll/legal requirements. Retain enough evidence to explain:

- source files used;
- mapping version;
- rule-library version;
- audit date range;
- run identifier/time;
- readiness/review findings; and
- subsequent corrections.

Do not commit real payroll exports, API secrets or controlled employee evidence to the public/source-code repository.

## Upgrade procedure

For either platform:

1. update the approved repository version;
2. update/deploy platform definitions and the AuditHero package;
3. run Setup;
4. run Self Test;
5. rerun a known payroll period;
6. compare results to the previous approved version; and
7. only then resume scheduled production audits.
