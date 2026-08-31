# AuditHero

AuditHero is a payroll audit solution for the **Social, Community, Home Care and Disability Services Industry Award 2010 (SCHADS / MA000100)**. It can reconstruct expected Award entitlements from timesheets and employment history, compare them with payroll, highlight evidence gaps, and support both routine payroll assurance and historical reviews.

AuditHero runs in either **Microsoft Fabric** or **Databricks**. Day-to-day users work from the platform UI: upload files, run pipelines/jobs, review exceptions and open the dashboard. Command-line tools are optional and are mainly useful for administrators who want automated deployments.

> AuditHero is compliance-support software, not legal advice. Before making remediation or recovery decisions, validate Award coverage, classifications, historical industrial instruments and representative calculations with appropriately qualified people.

## What an operator normally does

If your payroll, HR or timekeeping exports use their own column names, the normal workflow is:

1. **Upload the original CSV/Excel exports.** Do not reshape them by hand first.
2. Run **AuditHero - Build Source Mapping Workbook**.
3. Review the generated Excel mapping workbook and match your source fields to AuditHero fields.
4. Run **AuditHero - Convert Source Files**. AuditHero creates the standard input files and runs readiness checks.
5. Run **AuditHero - Audit Uploaded CSV Excel** (Databricks) or **AuditHero - Uploaded Files Audit Pipeline** (Fabric) for the required dates.
6. Review results in **Databricks AI/BI** or **Power BI**.

If your files already use the AuditHero standard workbook/CSV format, you can skip the mapping and conversion steps.

## Choose your platform

| | Microsoft Fabric | Databricks |
|---|---|---|
| Main user interface | Fabric workspace and Data Factory pipelines | Jobs & Pipelines / Workflows |
| File storage | Lakehouse Files | Unity Catalog Volumes |
| Reporting | Direct Lake + Power BI | Databricks AI/BI |
| First install | UI-first guide available | UI-first bundle deployment |
| CSV/Excel field mapping | Yes | Yes |
| Employment Hero API | Optional | Optional |
| CLI required for daily use | No | No |

Start with:

- **Fabric:** [Install AuditHero in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md)
- **Databricks:** [Install AuditHero in Databricks](docs/INSTALL_DATABRICKS_UI.md)

## Data sources

### Upload files — recommended starting point

AuditHero accepts a single canonical workbook named `audithero_input.xlsx` or separate canonical CSV/Excel files. You can also upload **arbitrary exports** from payroll, HR and timekeeping systems and use the source-mapping pipelines to convert them.

Core audit datasets are:

- employees;
- effective-dated pay/classification details;
- employment history; and
- timesheets.

Rostered shifts, pay runs and payroll earnings are recommended because they make overtime and actual-versus-expected reconciliation more complete. Historical instrument coverage, part-time patterns and other evidence can be supplied in the same workbook or as separate controlled files.

See [Audit data requirements](docs/AUDIT_DATA_REQUIREMENTS.md) and [Importing and mapping CSV/Excel files](docs/IMPORT_AND_FIELD_MAPPING.md).

### Employment Hero API — optional automation

Employment Hero HR and Payroll API connectivity can be enabled later. It is not required to install AuditHero or run uploaded-file audits. API mode is useful once you want automated extraction and scheduled recurring audits.

## What AuditHero checks

The shared calculation engine includes effective-dated SCHADS rates and conditions for the supported rule library, including relevant ordinary penalties, casual loading, minimum engagement, roster/daily/period overtime, broken shifts, sleepovers, public holidays, shiftwork, part-time pattern controls, rest-after-overtime, meal events, supplemental events, TOIL and industrial-instrument coverage controls.

When AuditHero cannot establish a result from the available evidence, it uses **`REQUIRES_REVIEW`** instead of guessing. Review items are kept separate from confirmed remediation totals.

See [SCHADS rules and evidence](docs/SCHADS_RULES_AND_EVIDENCE.md).

## Result statuses

Typical pay-period results are:

- `COMPLIANT` — actual auditable pay is within tolerance of expected pay;
- `UNDERPAID` — confirmed auditable pay is below expected pay;
- `OVERPAID` — confirmed auditable pay is above expected pay;
- `REQUIRES_REVIEW` — evidence or rule allocation is not reliable enough for an automated conclusion; and
- `ACTUAL_PAY_UNAVAILABLE` — expected entitlements were calculated but usable payroll earnings were not supplied.

See [Understanding AuditHero results](docs/UNDERSTANDING_RESULTS.md).

## Documentation

The documentation is organized for operators and administrators:

- [Documentation home](docs/README.md)
- [Quick start](QUICKSTART.md)
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
- [Optional CLI and automation](docs/CLI_AND_AUTOMATION.md)

## For administrators

The effective-dated Award rule library lives under `rules/MA000100/`. Fabric and Databricks use the same Python calculation package and the same rule packs, so calculation logic is not maintained separately by platform.

The platform UI should be the normal operating surface. CLI scripts, REST deployment tooling and CI/CD are retained as optional automation tools; see [CLI and automation](docs/CLI_AND_AUTOMATION.md).
