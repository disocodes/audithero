# AuditHero

AuditHero is a payroll audit solution for the **Social, Community, Home Care and Disability Services Industry Award 2010 (SCHADS / MA000100)**. It reconstructs expected Award entitlements from employment, roster, timekeeping and payroll evidence, compares expected pay with actual auditable pay, and separates confirmed reconciliation results from items that require human review.

AuditHero can run in **Microsoft Fabric** or **Databricks**.

> AuditHero is compliance-support software, not legal advice. Validate Award coverage, classifications, industrial-instrument history and representative calculations before using results for remediation, recovery or payroll changes.

## Typical workflow

### CSV / Excel

1. Export payroll, HR, rostering and timekeeping files.
2. Upload the files to the AuditHero landing area.
3. Run **AuditHero - Build Source Mapping Workbook** for a new source layout.
4. Review and approve the generated mapping workbook.
5. Run **AuditHero - Convert Mapped Files and Run Audit** for the required dates.
6. Review `COMPLIANT`, `UNDERPAID`, `OVERPAID`, `REQUIRES_REVIEW` and `ACTUAL_PAY_UNAVAILABLE` results.
7. Review detailed evidence before using any result for remediation.

After a source layout has been mapped once, later payroll periods normally reuse the same approved mapping.

### Employment Hero API

When Employment Hero API access is configured, AuditHero can extract source data directly for monthly and historical audits. Uploaded-file auditing remains available without Employment Hero credentials.

## Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates the AuditHero Lakehouse, Environment, notebooks, pipelines, semantic model and Power BI report, then runs Setup and Self Test.

See [Install AuditHero in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md).

## Databricks

Import `installers/Databricks_Install_AuditHero.py` into the target Databricks workspace and choose **Run all**.

The installer creates or updates:

- `/Shared/AuditHero` workspace files and notebooks;
- AuditHero Jobs;
- the `schads_payroll` Unity Catalog and landing Volume;
- Silver normalized-evidence tables;
- Gold audit-result tables;
- governed Unity Catalog metric views;
- the **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard; and
- the **AuditHero - Payroll Compliance** Genie space.

See [Install AuditHero in Databricks](docs/INSTALL_DATABRICKS_UI.md).

## Databricks monthly file workflow

After installation:

1. Upload source files to `/Volumes/schads_payroll/bronze/landing/import/raw`.
2. For a new source layout, run **AuditHero - Build Source Mapping Workbook**.
3. Save the approved workbook as `/Volumes/schads_payroll/bronze/landing/import/source_mapping.xlsx`.
4. Run **AuditHero - Convert Mapped Files and Run Audit** and enter the audit start and end dates.
5. Review the AI/BI dashboard and use Genie for governed analysis of completed audit results.

AuditHero stores normalized source evidence in Silver Delta tables and audit outputs in Gold Delta tables. Genie reads the governed result and semantic layers; it does not calculate SCHADS entitlements.

## Data requirements

Minimum audit data normally includes:

- employees;
- effective-dated pay and classification information;
- employment history; and
- timesheets.

Rostered shifts, payroll earnings, leave, public-holiday data and other evidence improve the completeness of the audit. Some SCHADS conditions require evidence that may not exist in a standard payroll export.

See [Audit data requirements](docs/AUDIT_DATA_REQUIREMENTS.md) and [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md).

## Result statuses

- `COMPLIANT` — actual auditable pay is within tolerance of expected pay and no unresolved review condition prevents the conclusion.
- `UNDERPAID` — confirmed auditable pay is below expected pay.
- `OVERPAID` — confirmed auditable pay is above expected pay.
- `REQUIRES_REVIEW` — available evidence is insufficient for a reliable automated conclusion.
- `ACTUAL_PAY_UNAVAILABLE` — expected entitlements were calculated but usable actual payroll earnings were not supplied.

`REQUIRES_REVIEW` items are not treated as confirmed underpayments.

See [Understanding AuditHero results](docs/UNDERSTANDING_RESULTS.md).

## Upgrade and uninstall

### Microsoft Fabric

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

### Databricks

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

A standard uninstall preserves payroll and audit storage. Permanent data deletion requires the explicit confirmation phrase `DELETE AUDITHERO DATA` in the uninstaller notebook.

## Documentation

- [Quick start](QUICKSTART.md)
- [Documentation home](docs/README.md)
- [Install in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md)
- [Install in Databricks](docs/INSTALL_DATABRICKS_UI.md)
- [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](docs/RUNNING_AUDITS.md)
- [Understanding results](docs/UNDERSTANDING_RESULTS.md)
- [SCHADS rules and evidence](docs/SCHADS_RULES_AND_EVIDENCE.md)
- [Notebook reference](docs/NOTEBOOK_REFERENCE.md)
- [Administration and security](docs/ADMINISTRATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [CLI and automation](docs/CLI_AND_AUTOMATION.md)
