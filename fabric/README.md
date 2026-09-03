# AuditHero on Microsoft Fabric

AuditHero is installed, upgraded, and operated from the Microsoft Fabric workspace.

## Installation

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates:

- `AuditHero_Lakehouse`;
- `AuditHero_Environment`;
- AuditHero operational notebooks;
- Data Factory pipelines;
- the configured monthly schedule;
- the Direct Lake semantic model; and
- the **AuditHero - SCHADS Payroll Compliance** Power BI report.

The following administration notebooks are also installed:

- **AuditHero - Install or Upgrade**
- **AuditHero - Uninstall**

See [Install AuditHero in Microsoft Fabric](../docs/INSTALL_FABRIC_UI.md).

## Standard CSV/Excel audit workflow

1. Upload ordinary CSV/XLSX files to `AuditHero_Lakehouse / Files / import / raw`.
2. Run **AuditHero - Auto Audit Uploaded Files**.
3. Open **AuditHero - SCHADS Payroll Compliance** in Power BI.

Automatic intake can combine information from multiple CSV files and Excel sheets. A basic timesheet needs an employee name or identifier plus shift start and end. Additional files or columns enrich the audit with hours, employee rates, rate effective dates, employment type, classification, location, work type, pay-period dates and explicit actual payroll amounts.

## Effective-dated employee rates

Employee base/hourly rates may be:

- included on individual timesheet rows; or
- supplied in a separate rate-history CSV/XLSX file.

Multiple rates for the same employee are retained. For each shift, AuditHero aligns the latest supplied rate effective on or before the shift date and compares it with the effective SCHADS minimum for the selected classification scenario.

A supplied hourly/base rate is evidence for base-rate compliance. It is not treated as complete actual shift pay because penalties, overtime, allowances and other components may apply separately.

## Complete Award analysis with limited setup

The automatic audit produces:

- a definitive audit where employee classification and employment facts are known; and
- selectable Award scenarios across SCHADS classification streams, levels, pay points and employment types.

Supported result areas include the effective-dated rules implemented by the installed AuditHero rule library, including:

- classification and base-rate compliance;
- ordinary penalties and shiftwork;
- weekends and public holidays;
- overtime;
- minimum engagement;
- rest between work;
- meal-break findings;
- sleepovers;
- broken shifts;
- allowances;
- TOIL; and
- other controlled events.

Material facts that cannot be established safely are shown as evidence-required or `REQUIRES_REVIEW` findings. They do not prevent unrelated Award calculations.

## Power BI report

The Direct Lake report is organized around Award investigation areas:

- **Award Explorer** — select employee, SCHADS stream, level, pay point and employment type and review the calculated scenario for the supplied shifts.
- **Classification & Historical Rates** — review effective-dated supplied employee rates against effective SCHADS minimums.
- **Penalties & Shiftwork** — inspect penalty, shiftwork, public-holiday and minimum-engagement components.
- **Overtime** — inspect overtime hours, multipliers, rates, calculated amounts and evidence.
- **Rest & Meal Breaks** — review required rest, actual rest, shortfalls, supported rest-after-overtime payment consequences and meal-break findings.
- **Sleepovers, Broken Shifts & Allowances** — review those Award components and associated evidence requirements.
- **Actual vs Expected** — review definitive pay-period reconciliation where suitable actual payroll evidence is available.
- **Evidence Required** — review facts that could not be safely established from the uploaded source data.
- **Definitive Shift Investigation** — inspect governed shift-level calculations based on known employee facts.
- **Rules & Audit History** — review effective-dated rule coverage and audit execution history.

Interactive slicers are provided on the Award pages for employee, stream, level, pay point, employment type and relevant status/criteria fields.

## Advanced source mapping

Use the advanced mapping workflow when automatic intake cannot identify an unusual source layout reliably:

- **AuditHero - Build Source Mapping Workbook (Advanced)**
- **AuditHero - Convert Source Files (Advanced)**
- **AuditHero - Convert Mapped Files and Run Audit (Advanced)**
- **AuditHero - Canonical Files Audit (Advanced)**

Employment Hero credentials are required only for Employment Hero API workflows.

## Upgrade

Open **AuditHero - Install or Upgrade** and choose **Run all**. Upgrade refreshes the managed notebooks, pipelines, package, effective-dated rule library, Direct Lake semantic model and Power BI report.

## Uninstall

Open **AuditHero - Uninstall** and choose **Run all**.

A standard uninstall removes AuditHero-managed workspace resources while preserving `AuditHero_Lakehouse` and its payroll/audit data. Permanent data removal requires the explicit confirmation phrase `DELETE AUDITHERO DATA` in the uninstaller notebook.

## Main documentation

- [Quick start](../QUICKSTART.md)
- [Install, upgrade, and remove](../docs/INSTALL_FABRIC_UI.md)
- [Import and field mapping](../docs/IMPORT_AND_FIELD_MAPPING.md)
- [Audit data requirements](../docs/AUDIT_DATA_REQUIREMENTS.md)
- [Running audits](../docs/RUNNING_AUDITS.md)
- [Understanding results](../docs/UNDERSTANDING_RESULTS.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Notebook reference](../docs/NOTEBOOK_REFERENCE.md)
- [CLI and automation](../docs/CLI_AND_AUTOMATION.md)
