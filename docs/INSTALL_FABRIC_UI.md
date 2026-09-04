# Install AuditHero in Microsoft Fabric

AuditHero can be installed from the Microsoft Fabric user interface with one bootstrap notebook. The installer creates or updates the required Lakehouse, Environment, notebooks, Data Factory pipelines, Direct Lake semantic model and Power BI report.

## Requirements

The Fabric workspace must provide:

- active Fabric capacity;
- permission to create/manage workspace items; and
- permission to run Fabric notebooks.

Employment Hero credentials are not required for installation or uploaded-file audits.

## First installation

1. Import `installers/Fabric_Install_AuditHero.py` into the target workspace.
2. Review the installation settings.
3. Choose **Run all**.
4. Confirm Setup and Self Test succeed before using production payroll evidence.

Default settings include:

```python
release_ref = "main"
lakehouse_name = "AuditHero_Lakehouse"
environment_name = "AuditHero_Environment"
key_vault_url = ""
monthly_schedule_enabled = False
```

Leave `key_vault_url` blank for file-based audits. Keep the monthly schedule disabled until a representative period has been validated.

## Resources created

The installer creates or updates:

- `AuditHero_Lakehouse`;
- `AuditHero_Environment`;
- Setup/Self Test and operator notebooks;
- administration notebooks;
- standard preview and reviewed-audit pipelines;
- Advanced Mapping/canonical pipelines;
- optional API historical/monthly pipelines;
- the Direct Lake semantic model; and
- **AuditHero - SCHADS Payroll Compliance** in Power BI.

## First CSV / Excel audit

### 1. Upload source evidence

Upload unchanged CSV/XLSX exports to:

`AuditHero_Lakehouse / Files / import / raw`

### 2. Preview and prepare

Run:

**AuditHero - Preview Uploaded Files**

Review the displayed interpretation and:

`Files/auto_input/auto_intake_preview.csv`

The preview pipeline prepares canonical candidate files and `auto_intake_manifest.json`; it does not start entitlement calculation.

### 3. Continue or correct

If the interpretation is correct, run:

**AuditHero - Audit Reviewed Uploaded Files**

The prepared-file manifest supplies the detected audit window unless start/end dates are explicitly provided.

If the interpretation is wrong or incomplete, run:

**AuditHero - Build Source Mapping Workbook (Advanced)**

Review `source_mapping_draft.xlsx`, use the controlled dropdowns to correct file roles/fields/values, save the approved workbook as `source_mapping.xlsx`, and run:

**AuditHero - Convert Mapped Files and Run Audit (Advanced)**

### 4. Review results

Open **AuditHero - SCHADS Payroll Compliance** in Power BI and review summary measures together with detailed calculation/evidence tables.

## Advanced canonical workflow

Use **AuditHero - Convert Source Files (Advanced)** when conversion/readiness should be checked without starting calculation.

Use **AuditHero - Canonical Files Audit (Advanced)** when canonical AuditHero files already exist in `Files/input`.

## Routine file-based process

For each period:

1. retain/archive the original evidence batch;
2. upload the new batch to `Files/import/raw`;
3. run **AuditHero - Preview Uploaded Files**;
4. review the interpretation and warnings;
5. run **AuditHero - Audit Reviewed Uploaded Files** if correct, or use Advanced Mapping if required; and
6. review Power BI and detailed evidence findings.

## Upgrade

Open **AuditHero - Install or Upgrade**, set `release_ref` to the approved release, and choose **Run all**.

Validate a known payroll period after upgrade before resuming recurring production audits.

## Uninstall

Open **AuditHero - Uninstall** and choose **Run all**.

A standard uninstall removes AuditHero-managed application resources while preserving Lakehouse payroll/audit storage. Permanent deletion requires:

```python
delete_audit_data = True
confirmation = "DELETE AUDITHERO DATA"
```

## Optional Employment Hero API

To enable API extraction, configure Azure Key Vault and the required Employment Hero secrets. Uploaded-file workflows remain available without API credentials. Keep recurring schedules disabled until connectivity, readiness and a representative period have been validated.

See [Administration](ADMINISTRATION.md) for permissions, schedules, mappings and API configuration.
