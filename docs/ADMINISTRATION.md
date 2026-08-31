# AuditHero administration

This guide is for people who maintain an installed AuditHero environment. Day-to-day payroll and audit users should normally use the platform jobs, pipelines and reports described in the [Quick start](../QUICKSTART.md).

## Roles and access

Separate responsibilities where practical:

- **Platform administrator:** installation, workspace permissions, upgrades and removal.
- **Payroll data administrator:** source mappings, pay-category treatment and controlled evidence registers.
- **Audit operator/reviewer:** runs audits and reviews findings.

Payroll data is sensitive. Apply least-privilege access to Lakehouse/Volumes, output tables and dashboards.

## First installation

Use the bootstrap notebook for the selected platform:

- Microsoft Fabric: `installers/Fabric_Install_AuditHero.py`
- Databricks: `installers/Databricks_Install_AuditHero.py`

The bootstrap creates or updates the AuditHero application and runs Setup and Self Test automatically. It also installs permanent administration notebooks inside the platform so the repository bootstrap does not need to be imported again for routine upgrades or removal.

## Upgrading AuditHero

After the first installation, use the administration notebook already installed in the platform.

### Microsoft Fabric

Open **AuditHero - Install or Upgrade** in the AuditHero workspace.

### Databricks

Open:

`/Shared/AuditHero/admin/AuditHero - Install or Upgrade`

Set `release_ref` to the approved AuditHero version when required, then choose **Run all**. The installer updates the application and reruns Setup and Self Test.

After an upgrade, validate one known payroll period before resuming production or recurring audits.

## Removing AuditHero

Use the installed **AuditHero - Uninstall** notebook.

### Microsoft Fabric

Open **AuditHero - Uninstall** in the AuditHero workspace.

### Databricks

Open:

`/Shared/AuditHero/admin/AuditHero - Uninstall`

A normal uninstall removes AuditHero application resources while preserving the payroll/audit Lakehouse or catalog.

Permanent data deletion requires both settings below before running the uninstaller:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

Before permanent deletion, follow the organisation's payroll-record retention, approval and backup requirements.

## Source mapping governance

Treat `source_mapping.xlsx` as controlled configuration. It determines how source evidence is interpreted before the SCHADS engine runs.

When a source export changes:

1. upload a representative sample of the new layout;
2. run **AuditHero - Build Source Mapping Workbook**;
3. review and version the approved mapping;
4. convert a known payroll period;
5. review the conversion report and File Readiness findings; and
6. manually validate representative audit results.

Do not modify Award calculation code to compensate for a source-system column change.

## Rule-library updates

The AuditHero rule packs are stored under `rules/MA000100/` in the installed release.

When an approved rate or condition version is introduced:

1. install the approved AuditHero release in a non-production workspace where required;
2. run the installer Self Test;
3. run a known payroll period;
4. review representative calculations and rule coverage; and
5. promote the approved version according to the organisation's release process.

Historical rule packs should not be overwritten merely to apply a new current rate.

## Employment Hero API (optional)

Uploaded-file auditing does not require Employment Hero credentials.

### Microsoft Fabric

Store API secrets in Azure Key Vault. Do not place secret values in source files, notebook parameters or Power BI.

### Databricks

Use Databricks Secrets. Uploaded-file jobs remain available without API configuration.

API connectivity is an ingestion option. It does not replace controlled evidence that cannot be established reliably from the source system.

## Schedules

Recurring payroll audits are installed disabled/paused by default. Enable a schedule only after:

- one representative payroll period has been validated;
- the source mapping is stable;
- required evidence registers are maintained; and
- the payroll/audit team knows how to resolve `REQUIRES_REVIEW` findings.

For recurring file-based auditing, ensure the current source exports are uploaded before the scheduled conversion/audit run.

## Retention and audit trail

Set retention according to the organisation's payroll and legal requirements. Retain enough evidence to explain:

- source files used;
- mapping version;
- rule-library/AuditHero release version;
- audit date range;
- run identifier and run time;
- readiness/review findings; and
- subsequent corrections or approvals.

Do not commit real payroll exports, API secrets or controlled employee evidence to the source-code repository.