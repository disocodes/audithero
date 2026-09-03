# AuditHero

AuditHero is a payroll audit solution for the **Social, Community, Home Care and Disability Services Industry Award 2010 (SCHADS / MA000100)**. It reconstructs expected Award entitlements from available employment and timekeeping evidence, evaluates Award conditions, compares supplied employee rates with effective SCHADS minimums, reconciles actual payroll where suitable payroll evidence is available, and keeps calculated outcomes separate from findings that require additional evidence.

AuditHero supports **Microsoft Fabric** and **Databricks** deployments.

> AuditHero is compliance-support software, not legal advice. Validate Award coverage, employee classifications, industrial-instrument history, representative calculations, and material review findings before using results for remediation, recovery, or payroll changes.

## Standard CSV/Excel workflow

For ordinary file-based audits:

1. export the available timesheet, employee, rate and payroll files;
2. upload the original CSV/XLSX files to the AuditHero raw landing area;
3. run **AuditHero - Auto Audit Uploaded Files**; and
4. open the AuditHero dashboard/report to review Award outcomes and supporting evidence.

A basic timesheet can be identified from an employee name or identifier together with shift start and end values. AuditHero uses additional fields and files when available, including worked hours, employee rates, rate effective dates, employment type, classification, work location, work type, pay-period dates and explicit payroll amounts.

The automatic workflow calculates all supported outcomes that can be determined from the supplied evidence. Facts that cannot be established safely are reported as evidence or review findings rather than being assumed.

### Effective-dated employee rates

Employee rates can be supplied:

- on individual timesheet rows; or
- in a separate CSV/XLSX rate-history file.

A rate-history file can contain multiple rate changes for the same employee, for example:

| Employee Name | Effective Date | Hourly Rate |
|---|---|---:|
| Example Employee | 2025-01-01 | 34.20 |
| Example Employee | 2025-07-01 | 35.80 |
| Example Employee | 2026-07-01 | 37.40 |

AuditHero aligns the employee rate effective on each shift date with the applicable effective-dated SCHADS minimum. This base-rate comparison is kept separate from full actual-pay reconciliation because an hourly base rate does not by itself prove what was paid for penalties, overtime, allowances or other components.

## Award analysis

File audits produce two related result sets:

- **Definitive audit** — uses known employee classification and employment facts where available.
- **Award scenarios** — recalculates the supplied shifts across selectable SCHADS classification streams, levels, pay points and employment types. This supports analysis where classification data is incomplete or where alternative classifications need to be compared.

Supported calculation and investigation areas include the effective-dated rules implemented in the installed rule library, including base rates, ordinary penalties, shiftwork, weekends, public holidays, overtime, minimum engagement, rest between work, meal-break findings, sleepovers, broken shifts, allowances, TOIL and other controlled events.

Scenario results do not establish an employee's legal classification by themselves. They show the calculated Award outcome under the selected scenario.

## Interactive reporting

The reporting experience is organized around Award investigation areas rather than raw result tables. Depending on the platform, the report/dashboard provides pages or views for:

- Award Explorer;
- Classification & Historical Rates;
- Penalties & Shiftwork;
- Overtime;
- Rest & Meal Breaks;
- Sleepovers, Broken Shifts & Allowances;
- Actual vs Expected;
- Evidence Required;
- Definitive Shift Investigation; and
- Rules & Audit History.

Use employee, SCHADS stream, level, pay point, employment-type and status filters to move between scenarios and underlying shift evidence.

## Advanced source mapping

The source-mapping workflow remains available for unusual exports that cannot be identified reliably by automatic intake. The advanced tools are:

- **AuditHero - Build Source Mapping Workbook (Advanced)**;
- **AuditHero - Convert Source Files (Advanced)**; and
- **AuditHero - Convert Mapped Files and Run Audit (Advanced)**.

## Employment Hero API workflow

Employment Hero API extraction is optional. When configured, AuditHero can extract source data directly for recurring monthly audits and selected historical date ranges. Uploaded-file auditing remains available without Employment Hero credentials.

## Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates the AuditHero Lakehouse, Environment, notebooks, pipelines, Direct Lake semantic model, and Power BI report, then runs the installation initialization sequence.

Standard file workflow:

1. upload ordinary CSV/XLSX files to `Files/import/raw` in the AuditHero Lakehouse;
2. run **AuditHero - Auto Audit Uploaded Files**; and
3. open **AuditHero - SCHADS Payroll Compliance**.

See [Install AuditHero in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md).

## Databricks

Import `installers/Databricks_Install_AuditHero.py` into the target Databricks workspace and choose **Run all**.

The installer creates or updates:

- `/Shared/AuditHero` workspace files and notebooks;
- AuditHero Jobs;
- the `schads_payroll` Unity Catalog and landing Volume;
- Silver normalized-evidence tables;
- Gold definitive and Award-scenario result tables;
- governed Unity Catalog metric views;
- the **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard; and
- the **AuditHero - Payroll Compliance** Genie space.

Standard file workflow:

1. upload ordinary CSV/XLSX files to `/Volumes/schads_payroll/bronze/landing/import/raw`;
2. run **AuditHero - Auto Audit Uploaded Files**; and
3. review the AI/BI dashboard or ask governed questions in Genie.

See [Install AuditHero in Databricks](docs/INSTALL_DATABRICKS_UI.md).

## Result statuses

- `COMPLIANT` — actual auditable pay is within tolerance of expected pay and no unresolved review condition prevents the conclusion.
- `UNDERPAID` — confirmed auditable pay is below expected pay.
- `OVERPAID` — confirmed auditable pay is above expected pay.
- `REQUIRES_REVIEW` — a material factual or evidence requirement prevents a reliable automated conclusion for the affected item.
- `ACTUAL_PAY_UNAVAILABLE` / `ENTITLEMENT_ONLY` — expected entitlement can be calculated, but suitable actual-pay evidence is not available for definitive reconciliation.

`REQUIRES_REVIEW` items are not treated as confirmed underpayments.

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
