# AuditHero quick start

Use this guide to install AuditHero and complete a first CSV/Excel SCHADS audit. Employment Hero credentials are required only for Employment Hero API workflows.

## 1. Install AuditHero

### Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

### Databricks

Import `installers/Databricks_Install_AuditHero.py` into the target Databricks workspace and choose **Run all**.

The installer prepares the required storage, effective-dated rule library, operational jobs or pipelines, reporting assets, and administration notebooks.

Detailed installation guides:

- [Microsoft Fabric installation](docs/INSTALL_FABRIC_UI.md)
- [Databricks installation](docs/INSTALL_DATABRICKS_UI.md)

## 2. Prepare the available files

AuditHero's standard file workflow is designed for ordinary CSV/XLSX exports. A basic timesheet should contain an employee name or identifier and enough date/time information to establish shift start and end.

Useful additional fields or files include:

- worked hours;
- unpaid break minutes;
- employee hourly/base rate;
- rate effective date;
- employment type;
- classification or Award level;
- work state/location;
- role or work type;
- pay-period dates; and
- explicit payroll or shift amounts.

CSV and Excel files can be uploaded together. Excel workbooks may contain multiple sheets.

### Rate histories

Employee rates can be embedded in timesheet rows or supplied separately. A separate rate-history file can contain multiple changes for the same employee:

| Employee Name | Effective Date | Hourly Rate |
|---|---|---:|
| Example Employee | 2025-01-01 | 34.20 |
| Example Employee | 2025-07-01 | 35.80 |
| Example Employee | 2026-07-01 | 37.40 |

AuditHero aligns each shift with the latest supplied employee rate effective on or before that shift date.

## 3. Upload the files

### Microsoft Fabric

Upload source files to:

`AuditHero_Lakehouse / Files / import / raw`

### Databricks

Upload source files to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

## 4. Run the automatic file audit

Run:

**AuditHero - Auto Audit Uploaded Files**

The workflow automatically:

1. identifies usable timesheet and employee/rate files;
2. normalizes employee and shift records;
3. retains effective-dated employee rate history;
4. calculates the definitive audit where employee facts are known;
5. calculates selectable SCHADS classification and employment-type scenarios;
6. evaluates supported Award criteria including penalties, overtime, rest/break findings, sleepovers, broken shifts, minimum engagement and allowances;
7. reconciles actual payroll only when suitable actual-pay evidence is available;
8. stores governed results; and
9. refreshes the reporting layer.

Missing optional facts do not prevent unrelated Award calculations. Material facts that cannot be established from the uploaded evidence are reported in **Evidence Required** or `REQUIRES_REVIEW` findings.

## 5. Review the Award analysis

### Microsoft Fabric

Open **AuditHero - SCHADS Payroll Compliance** in Power BI.

### Databricks

Open:

- **AuditHero - SCHADS Payroll Compliance** in AI/BI; or
- **AuditHero - Payroll Compliance** in Genie.

The reporting layer is organized around Award investigation areas such as:

- Award Explorer;
- Classification & Historical Rates;
- Penalties & Shiftwork;
- Overtime;
- Rest & Meal Breaks;
- Sleepovers, Broken Shifts & Allowances;
- Actual vs Expected;
- Evidence Required; and
- Definitive Shift Investigation.

Use the employee, SCHADS stream, level, pay point and employment-type controls to compare scenarios for the same supplied shifts.

## 6. Understand base-rate and actual-pay results

A supplied hourly/base rate is used to compare the employee's rate with the effective SCHADS minimum for the selected scenario. It is not treated as complete actual shift pay because penalties, overtime and other components may apply.

Full `UNDERPAID`, `OVERPAID` or `COMPLIANT` reconciliation requires suitable actual-pay evidence. When actual payroll is unavailable, AuditHero can still calculate expected Award entitlements and rate-compliance outcomes.

Typical statuses include:

- `COMPLIANT`
- `UNDERPAID`
- `OVERPAID`
- `REQUIRES_REVIEW`
- `ACTUAL_PAY_UNAVAILABLE`
- `ENTITLEMENT_ONLY`

A `REQUIRES_REVIEW` result is not a confirmed underpayment.

## 7. Validate representative cases

Before using a large historical result set for remediation, review representative employee/shift cases relevant to the workforce, including applicable combinations of:

- classification and effective rate;
- Saturday/Sunday penalties;
- public holidays;
- shiftwork;
- overtime;
- minimum engagement;
- rest between work;
- meal breaks;
- broken shifts;
- sleepovers;
- allowances; and
- TOIL or other controlled events.

## 8. Repeat the file workflow

For later payroll periods:

1. upload the new ordinary CSV/XLSX files to the raw folder;
2. run **AuditHero - Auto Audit Uploaded Files**; and
3. review the refreshed report/dashboard and evidence findings.

No source-mapping workbook is required when automatic intake can identify the uploaded layout.

## Advanced source mapping

Use the advanced mapping workflow only when an unusual source layout cannot be identified reliably:

1. **AuditHero - Build Source Mapping Workbook (Advanced)**;
2. approve `source_mapping.xlsx`; and
3. **AuditHero - Convert Mapped Files and Run Audit (Advanced)**.

See [Import and field mapping](docs/IMPORT_AND_FIELD_MAPPING.md).

## Employment Hero API workflow

Employment Hero API connectivity can be configured for direct extraction and recurring monthly or historical audits.

- Fabric stores API secrets in Azure Key Vault.
- Databricks stores API secrets in Databricks Secrets.

See [Administration](docs/ADMINISTRATION.md).

## Upgrade or uninstall

### Microsoft Fabric

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

### Databricks

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

A standard uninstall preserves payroll and audit data. Permanent data removal requires the explicit `DELETE AUDITHERO DATA` confirmation.
