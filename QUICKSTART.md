# AuditHero quick start

Use this guide to install AuditHero and complete a first CSV/Excel SCHADS audit. Employment Hero credentials are required only for API workflows.

## 1. Install AuditHero

### Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

### Databricks

Import `installers/Databricks_Install_AuditHero.py` into the target Databricks workspace and choose **Run all**.

The installer prepares storage, the effective-dated rule library, operational pipelines/jobs, reporting assets, and administration notebooks.

Detailed installation guides:

- [Microsoft Fabric installation](docs/INSTALL_FABRIC_UI.md)
- [Databricks installation](docs/INSTALL_DATABRICKS_UI.md)

## 2. Prepare the source files

AuditHero's standard file workflow accepts ordinary CSV/XLSX exports. A usable timesheet should contain an employee name or identifier and enough date/time information to establish shift start and end.

Useful additional evidence includes:

- worked hours and unpaid breaks;
- employee base/hourly rates and effective dates;
- employment type;
- classification/Award level;
- work group or service stream;
- state/location;
- roster/work type;
- pay-period dates;
- payroll earning category, amount, hours and rate; and
- industrial-instrument, part-time, TOIL, break or other controlled evidence where applicable.

CSV and Excel files can be uploaded together. Excel workbooks may contain multiple sheets. Keep the original exports unchanged.

## 3. Upload the files

### Microsoft Fabric

Upload source files to:

`AuditHero_Lakehouse / Files / import / raw`

### Databricks

Upload source files to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

## 4. Preview and prepare

Run:

**AuditHero - Preview Uploaded Files**

AuditHero will:

1. inspect the uploaded CSV/XLSX files and sheets;
2. identify usable timesheet, employee/rate and clearly structured payroll earning data;
3. show the interpreted file roles and mapped source fields;
4. prepare canonical files in the platform's `auto_input` location;
5. write `auto_intake_preview.csv` and `auto_intake_manifest.json`; and
6. surface evidence warnings without starting the payroll audit.

Review the preview before continuing. Missing work group, employment type, industrial instrument, classification or payroll evidence is not invented.

## 5. Correct the interpretation only when necessary

If the preview is correct, no Advanced Mapping workbook is required.

If a file or field has been interpreted incorrectly, run:

**AuditHero - Build Source Mapping Workbook (Advanced)**

The workbook provides controlled sheets for:

- automatic preview;
- file-role/context correction;
- source-field mapping;
- value translation; and
- pay-category treatment when payroll earning categories are detected.

Use the workbook dropdowns rather than typing internal schema fields. Save the approved correction as `source_mapping.xlsx`, then run **AuditHero - Convert Mapped Files and Run Audit (Advanced)**.

## 6. Audit reviewed files

When the automatic preview is correct, run:

**AuditHero - Audit Reviewed Uploaded Files**

The prepared-file manifest supplies the detected audit window unless start/end dates are explicitly overridden.

The audit engine calculates supported definitive outcomes, Award scenarios and evidence findings. Actual-pay reconciliation is enabled only when payroll earning evidence is usable and every relevant pay category has an approved audit treatment.

## 7. Review readiness and results

AuditHero validates required datasets and values, key relationships, date/time evidence, shift intervals and controlled historical evidence. Blocking findings must be resolved where the selected workflow requires full audit readiness.

### Microsoft Fabric

Open **AuditHero - SCHADS Payroll Compliance** in Power BI.

### Databricks

Open:

- **AuditHero - SCHADS Payroll Compliance** in AI/BI; or
- **AuditHero - Payroll Compliance** in Genie.

Typical result statuses include:

- `COMPLIANT`
- `UNDERPAID`
- `OVERPAID`
- `REQUIRES_REVIEW`
- `ACTUAL_PAY_UNAVAILABLE`
- `ENTITLEMENT_ONLY`

`REQUIRES_REVIEW` is not a confirmed underpayment.

## 8. Validate representative cases

Before using a large historical result set for remediation, verify representative employee/shift cases covering the relevant workforce conditions, including classification and rate history, weekends/public holidays, shiftwork, overtime, minimum engagement, rest, meal breaks, broken shifts, sleepovers, allowances, TOIL, and any enterprise agreement/IFA/salary arrangement evidence.

## 9. Repeat for later payroll periods

For each new period:

1. retain/archive the original payroll evidence;
2. replace or clear the AuditHero raw landing batch as appropriate;
3. upload the new source files;
4. run **AuditHero - Preview Uploaded Files**;
5. review the interpretation;
6. run **AuditHero - Audit Reviewed Uploaded Files** when correct, or use Advanced Mapping when correction is needed; and
7. review the refreshed results and evidence findings.

## Employment Hero API workflow

Employment Hero API connectivity can be configured for direct extraction and recurring monthly/historical audits.

- Fabric stores configured API secrets in Azure Key Vault.
- Databricks uses Databricks Secrets.

The Databricks monthly schedule is paused by default. Enable recurring execution only after a representative period has been validated.

## Upgrade or uninstall

### Microsoft Fabric

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

### Databricks

- `/Shared/AuditHero/admin/AuditHero - Install or Upgrade`
- `/Shared/AuditHero/admin/AuditHero - Uninstall`

A standard uninstall preserves payroll and audit data. Permanent data removal requires the explicit `DELETE AUDITHERO DATA` confirmation.
