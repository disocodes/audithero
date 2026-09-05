# AuditHero

AuditHero is a payroll audit solution for the **Social, Community, Home Care and Disability Services Industry Award 2010 (SCHADS / MA000100)**. It reconstructs supported Award entitlements from employment and timekeeping evidence, evaluates effective-dated Award conditions, compares supplied employee base rates with supported SCHADS minimums, and reconciles actual payroll where suitable payroll earning evidence and approved pay-category treatment are available.

AuditHero supports **Microsoft Fabric** and **Databricks** deployments.

> AuditHero is compliance-support software, not legal advice. Validate Award coverage, employee classifications, industrial-instrument history, representative calculations, and material review findings before remediation, recovery, payroll changes, or legal conclusions.

## Operating principles

AuditHero is evidence-driven and fail-closed:

- original source files remain unchanged audit evidence;
- missing employment type, work group, classification, industrial instrument, state or payroll evidence is not silently invented;
- uncertain or unsupported facts produce review findings rather than definitive compliance conclusions;
- actual-pay reconciliation requires identifiable payroll earning lines and approved pay-category treatment;
- Award scenarios are analytical comparators and do not establish an employee's legal classification by themselves; and
- rule selection uses effective-dated rule packs for the audit period.

## Which job do I run?

The exact deployed job names and their intended order are shown below. For normal CSV/XLSX payroll auditing, use the **Standard uploaded-file path** unless the preview identifies a mapping problem.

### Standard uploaded-file path — normal monthly/operator workflow

1. Upload the original CSV/XLSX exports to the raw landing folder.
2. Run **AuditHero - Preview Uploaded Files**.
3. Review `auto_intake_preview.csv`, `auto_intake_manifest.json`, detected file roles, mapped fields and warnings.
4. If the interpretation is correct, run **AuditHero - Audit Reviewed Uploaded Files**.
5. Review the dashboard/report and detailed audit evidence.

Run order:

```text
AuditHero - Preview Uploaded Files
        ↓
review preview and warnings
        ↓
AuditHero - Audit Reviewed Uploaded Files
        ↓
review results
```

Do not use **AuditHero - Build Source Mapping Workbook (Advanced)** for every run. It is only required when the preview is incorrect, incomplete or needs additional controlled context.

### Advanced Mapping path — when the preview needs correction

1. Run **AuditHero - Preview Uploaded Files** first.
2. If the interpretation is not acceptable, run **AuditHero - Build Source Mapping Workbook (Advanced)**.
3. Review and correct the generated workbook using the controlled dropdowns.
4. Upload/save the approved workbook as `source_mapping.xlsx`.
5. Run **AuditHero - Convert Mapped Files and Run Audit (Advanced)**.
6. Review the resulting readiness, audit and reconciliation evidence.

Run order:

```text
AuditHero - Preview Uploaded Files
        ↓
preview needs correction
        ↓
AuditHero - Build Source Mapping Workbook (Advanced)
        ↓
review and approve source_mapping.xlsx
        ↓
AuditHero - Convert Mapped Files and Run Audit (Advanced)
        ↓
review results
```

**AuditHero - Convert Source Files (Advanced)** is available when conversion and readiness need to be inspected without running the payroll audit.

### Canonical-file path — when AuditHero canonical files already exist

Use this only when the input is already in AuditHero canonical format.

Databricks:

```text
AuditHero - File Readiness (Advanced)
        ↓
AuditHero - Audit Canonical CSV Excel (Advanced)
```

The canonical audit job already includes a readiness task. The standalone **AuditHero - File Readiness (Advanced)** job is useful when readiness needs to be inspected without starting an audit.

Fabric uses the deployed **AuditHero - Canonical Files Audit (Advanced)** pipeline, which performs readiness, audit and BI refresh in sequence.

### Employment Hero API — first-time or changed configuration

Run these in order:

```text
AuditHero - Employment Hero Connection Test (Optional API)
        ↓
AuditHero - API Audit Readiness (Optional API)
        ↓
AuditHero - Historical SCHADS Audit (Optional API)
```

Use **AuditHero - Historical SCHADS Audit (Optional API)** for a selected historical date range after connectivity and readiness have been validated.

### Employment Hero API — recurring monthly payroll

After a representative payroll period has been validated, run:

**AuditHero - Monthly Payroll Audit (Optional API)**

The recurring schedule is paused/disabled by default and should only be enabled after the organisation's mappings, evidence controls and representative results have been approved.

### Installation and validation jobs

These are installation/administration jobs rather than routine payroll-audit jobs:

- **AuditHero - Setup**
- **AuditHero - Self Test**

They are run during installation/upgrade validation and do not replace the operator workflows above.

### Databricks job inventory

The Databricks deployment currently defines these exact jobs:

- **AuditHero - Setup**
- **AuditHero - Self Test**
- **AuditHero - Preview Uploaded Files**
- **AuditHero - Audit Reviewed Uploaded Files**
- **AuditHero - Build Source Mapping Workbook (Advanced)**
- **AuditHero - Convert Source Files (Advanced)**
- **AuditHero - Convert Mapped Files and Run Audit (Advanced)**
- **AuditHero - File Readiness (Advanced)**
- **AuditHero - Audit Canonical CSV Excel (Advanced)**
- **AuditHero - Employment Hero Connection Test (Optional API)**
- **AuditHero - API Audit Readiness (Optional API)**
- **AuditHero - Historical SCHADS Audit (Optional API)**
- **AuditHero - Monthly Payroll Audit (Optional API)**

## Standard CSV / Excel workflow

The normal file workflow is preview-first:

1. export the available payroll, timesheet, employee, classification/rate, roster and supporting evidence files;
2. upload the original CSV/XLSX files to the AuditHero raw landing area;
3. run **AuditHero - Preview Uploaded Files**;
4. review the file/field interpretation and warnings;
5. if the interpretation is correct, run **AuditHero - Audit Reviewed Uploaded Files**;
6. if a role or field is wrong or additional context is needed, generate the **Advanced Mapping / Context Workbook**, correct the controlled dropdown selections, and run the mapped-file audit workflow; and
7. review the dashboard/report, exceptions and calculation evidence.

A basic timesheet can be recognised from an employee name or identifier together with shift start and end values. AuditHero uses additional evidence when present, including worked hours, employee rates, effective dates, employment type, classification, location, work type, pay periods, payroll earning categories and payroll amounts.

A standalone payroll earnings export is automatically recognised only when it contains a usable employee identifier, pay-period start, pay-period end, pay category and amount. Recognition of payroll data does **not** automatically approve its treatment for reconciliation.

## Public holidays and special holiday overrides

For manual/file-based audits, **normal Australian public holidays are generated automatically** for WA, NSW, VIC, QLD, SA, TAS, ACT and NT for the selected audit period. Operators do not need to upload a normal annual public-holiday calendar.

AuditHero uses the state on the employee/timesheet evidence to decide whether a shift falls on a public holiday. Missing state evidence can therefore prevent a complete public-holiday assessment and may produce a review finding.

### One-off, irregular or local public holidays

Use the optional canonical control file:

`public_holiday_overrides.csv`

This is for holidays that are not reliably represented by the normal statewide calendar, including one-off declared holidays, irregular regional holidays, local holidays and other approved special dates.

For the standard Databricks uploaded-file workflow, upload the source override with the other raw files before running **AuditHero - Preview Uploaded Files**. After preparation, the reviewed-file audit reads the canonical override from the prepared input area, normally:

```text
/Volumes/<catalog>/bronze/landing/auto_input/public_holiday_overrides.csv
```

Do **not** manually edit generated prepared files unless you are deliberately using the canonical-file workflow. The preferred standard workflow is: upload the override as source evidence → Preview → review → Audit Reviewed Uploaded Files.

Minimum columns:

| Column | Required | Meaning |
|---|---|---|
| `state` | Yes | Australian state/territory code, e.g. `WA`, `NSW`, `VIC` |
| `holiday_date` | Yes | Exact holiday date; operator-facing dates may use Australian day-first format such as `15-08-2025` |
| `holiday_name` | Yes | Descriptive holiday name |
| `holiday_location_key` | No | Blank for statewide; populate for a specific locality/site |
| `holiday_scope` | No | `STATEWIDE` or `LOCAL`; inferred when omitted |
| `source` | No | Evidence/source note; defaults to manual override where normalised |

Example — one-off statewide holiday:

```csv
state,holiday_date,holiday_name,holiday_location_key,holiday_scope,source
WA,15-08-2025,Special Public Holiday,,STATEWIDE,manual_override
```

Example — local/regional holiday:

```csv
state,holiday_date,holiday_name,holiday_location_key,holiday_scope,source
WA,15-08-2025,Kununurra Special Holiday,KUNUNURRA,LOCAL,manual_override
```

For a local override, the relevant timesheet must carry the **same `holiday_location_key`**. If the override contains `KUNUNURRA` but the timesheet has no matching location key, AuditHero will not apply that local holiday to the shift.

AuditHero filters holiday overrides to the selected audit window. A five-day audit therefore considers only overrides relevant to those five days; a multi-year audit considers the applicable overrides across that requested period.

The same dataset can also be supplied as `public_holiday_overrides.xlsx` / `.xlsm`, or as the `public_holiday_overrides` sheet in an AuditHero canonical workbook.

## Advanced Mapping / Context Workbook

Advanced Mapping is an optional correction layer, not replacement evidence and not a prerequisite for ordinary imports that are interpreted correctly.

The generated workbook contains:

- `preview` — automatic dataset/file interpretation;
- `file_context` — controlled file-role correction and evidence context;
- `field_mapping` — source-column to canonical-field mapping;
- `value_mapping` — controlled source-value translations; and
- `pay_category_treatment` when payroll earning categories are detected.

Source files and source fields are selected from workbook dropdowns wherever practical. `CONTEXT_ONLY` retains an uploaded item as evidence without using it as a canonical source. `IGNORE` excludes an item from mapping. Only one primary source may be selected for a canonical dataset.

## Evidence and audit readiness

AuditHero distinguishes between calculation availability and audit completeness. File Readiness validates, among other things:

- required datasets, columns and populated required values;
- valid dates, times and numeric evidence;
- unique employee and timesheet identifiers;
- employee-key referential integrity across canonical datasets;
- valid shift intervals;
- classification evidence;
- industrial-instrument history for controlled historical/remediation work;
- part-time pattern evidence where applicable;
- work-group and state evidence; and
- actual-pay and pay-category mapping availability.

Blocking readiness findings must be resolved for workflows that require full readiness. Missing optional actual-pay evidence can still permit entitlement-only analysis.

## Effective-dated employee rates

Employee rates can be supplied on individual source rows or in a separate effective-dated rate-history export. AuditHero aligns the source rate in force on a shift date with the applicable supported SCHADS minimum. A base hourly rate proves a nominal base rate only; it does not prove the complete amount actually paid for penalties, overtime, allowances or other components.

## Award analysis

File audits can produce two related result sets:

- **Definitive audit** — uses supported known employee facts and marks unresolved evidence as `REQUIRES_REVIEW`.
- **Award scenarios** — recalculates supplied shifts across supported SCHADS classification families, levels/pay points, work groups and employment types for investigation and comparison.

Supported calculation and investigation areas are determined by the installed effective-dated rule packs and engine modules, including base rates, ordinary penalties, shiftwork, weekends, public holidays, overtime, minimum engagement, rest between work, meal-break findings, sleepovers, broken shifts, allowances, TOIL and controlled supplemental events.

## Actual-pay reconciliation

Payroll earning lines must contain the required identifying fields and every pay category used in reconciliation must have an approved treatment:

- `AUDITABLE_WORK` — included in auditable worked pay;
- `ALLOWANCE` — treated as a controlled allowance component where supported; or
- `EXCLUDE` — excluded from the worked-pay comparator, for example an approved leave or reimbursement category.

Missing or ambiguous payroll evidence is not converted to a zero payment. It remains unavailable/review evidence.

## Employment Hero API workflow

Employment Hero integration is optional. When configured, AuditHero can extract source data directly for recurring monthly audits and selected historical date ranges. The API workflow uses the same effective-dated calculation engine and controlled evidence model. Uploaded-file auditing remains available without Employment Hero credentials.

## Microsoft Fabric

Import `installers/Fabric_Install_AuditHero.py` into the target Fabric workspace and choose **Run all**.

The installer creates or updates the AuditHero Lakehouse, Environment, notebooks, pipelines, Direct Lake semantic model, and Power BI report.

Standard file workflow:

1. upload original CSV/XLSX files to `Files/import/raw`;
2. run **AuditHero - Preview Uploaded Files**;
3. review the prepared-file interpretation;
4. run **AuditHero - Audit Reviewed Uploaded Files** when acceptable; or use the Advanced Mapping workflow if correction is needed; and
5. open **AuditHero - SCHADS Payroll Compliance**.

See [Install AuditHero in Microsoft Fabric](docs/INSTALL_FABRIC_UI.md).

## Databricks

Import `installers/Databricks_Install_AuditHero.py` into the target Databricks workspace and choose **Run all**.

The installer creates or updates AuditHero workspace files and notebooks, Jobs, Unity Catalog objects, Silver evidence tables, Gold result tables, governed semantic views, the **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard, and the **AuditHero - Payroll Compliance** Genie space.

Standard file workflow:

1. upload original CSV/XLSX files to `/Volumes/schads_payroll/bronze/landing/import/raw`;
2. run **AuditHero - Preview Uploaded Files**;
3. inspect `auto_intake_preview.csv` and preparation warnings;
4. run **AuditHero - Audit Reviewed Uploaded Files** when acceptable, or use the Advanced Mapping workflow for corrections; and
5. review the AI/BI dashboard or governed Genie analysis.

See [Install AuditHero in Databricks](docs/INSTALL_DATABRICKS_UI.md).

## Result statuses

- `COMPLIANT` — supported auditable pay is within tolerance of expected pay and no unresolved material review condition prevents the conclusion.
- `UNDERPAID` — confirmed auditable pay is below supported expected pay.
- `OVERPAID` — confirmed auditable pay is above supported expected pay.
- `REQUIRES_REVIEW` — a material factual, coverage, mapping or evidence requirement prevents a reliable automated conclusion.
- `ACTUAL_PAY_UNAVAILABLE` / `ENTITLEMENT_ONLY` — expected entitlement analysis is available but suitable actual-pay evidence is unavailable for definitive reconciliation.

`REQUIRES_REVIEW` is not a confirmed underpayment.

## Rule coverage

The bundled SCHADS rule library is effective-dated and the manifest declares its coverage and source packs. If no applicable rate, condition or allowance pack exists for a requested date/classification, AuditHero fails closed and surfaces review rather than extrapolating a rate.

Review `rules/MA000100/manifest.json` and [SCHADS rules and evidence](docs/SCHADS_RULES_AND_EVIDENCE.md) before relying on a historical period.

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
- [Architecture and code guide](docs/ARCHITECTURE.md)
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
