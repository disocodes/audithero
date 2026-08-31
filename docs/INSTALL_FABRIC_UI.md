# Install AuditHero in Microsoft Fabric

This guide uses the **Microsoft Fabric user interface** as the main installation and operating surface. The CLI/REST installer remains available as an optional administrator automation method; see [CLI and automation](CLI_AND_AUTOMATION.md).

## What a completed Fabric workspace contains

A complete AuditHero Fabric workspace contains:

- a schema-enabled Lakehouse named `AuditHero_Lakehouse`;
- an AuditHero Fabric Environment;
- setup and self-test notebooks;
- source mapping and conversion notebooks/pipelines;
- **AuditHero - Convert Mapped Files and Run Audit**;
- the direct canonical uploaded-file audit pipeline;
- optional Employment Hero API notebooks/pipelines;
- a Direct Lake semantic model; and
- the AuditHero Power BI report.

## Before you begin

You need:

- a Microsoft Fabric workspace on suitable capacity;
- permission to create Lakehouses, Environments, notebooks, pipelines, semantic models and reports; and
- access to the AuditHero repository/version approved by your organisation.

Azure Key Vault is **not** required for uploaded-file auditing. It is only required if optional Employment Hero API connectivity is enabled.

## UI-first installation

AuditHero can be installed without a local terminal. Because the repository contains ordinary notebook source plus deployment definitions rather than assuming one organisation-specific Fabric workspace layout, an administrator can create/import the items in the UI using the repository files as the controlled source.

The optional automated deployer creates the same items for organisations that prefer scripted deployment.

## 1. Create or select the Fabric workspace

Create a dedicated AuditHero workspace or select the workspace where payroll compliance data will be held. Restrict workspace access appropriately because payroll evidence can contain sensitive employee information.

## 2. Create the Lakehouse

From the workspace choose **New item → Lakehouse** and create:

`AuditHero_Lakehouse`

Use this as the default Lakehouse for AuditHero notebooks.

## 3. Create and publish the Environment

Create an Environment named:

`AuditHero_Environment`

Configure it using the dependency/runtime files in `fabric/environment/`.

The Environment requires the packages used by AuditHero, including:

- the AuditHero package/wheel;
- pandas;
- requests/holidays;
- `openpyxl` for Excel import/mapping; and
- Semantic Link Labs for the BI setup notebook.

Publish the Environment after changes.

For production use, keep the AuditHero package in the Environment rather than installing a different copy ad hoc in each notebook.

## 4. Add the AuditHero notebooks

Import/create notebooks from `fabric/notebooks/`, then attach them to both `AuditHero_Lakehouse` and `AuditHero_Environment`.

The main operator-facing notebooks are:

- **AuditHero - Build Source Mapping Workbook** (`03c_source_mapping_draft.py`)
- **AuditHero - Convert Source Files** (`03d_convert_source_files.py`)
- **AuditHero - File Readiness** (`03b_file_readiness.py`)
- **AuditHero - Audit Uploaded CSV Excel** (`04b_manual_file_audit.py`)

Administrator/optional notebooks include Setup, Self Test, API Connection/Readiness, API historical/monthly audit and Build BI.

Every notebook contains plain-language explanations before the major code sections so an administrator can see what the notebook is doing without reading the internal Python package first. See [Notebook reference](NOTEBOOK_REFERENCE.md).

## 5. Run Setup and Self Test

Run **AuditHero - Setup** once. It creates the Lakehouse schemas/reference/output structures used by the application.

Then run **AuditHero - Self Test**.

Do not proceed with production payroll evidence while the self-test is failing.

## 6. Create the source-mapping pipelines

Create these Data Factory pipelines in the Fabric UI.

### AuditHero - Build Source Mapping Workbook

Notebook: `03c_source_mapping_draft.py`

Suggested parameters:

- `source_root`: `/lakehouse/default/Files/import/raw`
- `draft_path`: `/lakehouse/default/Files/import/source_mapping_draft.xlsx`
- `overwrite`: `false`

This pipeline only inspects source structures and produces the editable mapping draft.

### AuditHero - Convert Source Files

Notebook: `03d_convert_source_files.py`

Suggested parameters:

- `source_root`: `/lakehouse/default/Files/import/raw`
- `mapping_path`: `/lakehouse/default/Files/import/source_mapping.xlsx`
- `output_root`: `/lakehouse/default/Files/input`
- `strict`: `true`

This pipeline converts the exports and runs readiness checks but does not need to run the payroll audit.

### AuditHero - Convert Mapped Files and Run Audit

Create a pipeline with three notebook activities:

1. **Convert Mapped Source Files** → `03d_convert_source_files.py`
2. **Run Audit on Converted Files** → `04b_manual_file_audit.py`, dependent on conversion success
3. **Refresh Direct Lake and Power BI** → `06_build_bi.py`, dependent on audit success

Expose these pipeline parameters:

- `source_root`
- `mapping_path`
- `output_root`
- `strict`
- `start_date`
- `end_date`

This is the normal operator pipeline after the mapping has been approved.

### Canonical uploaded-file audit pipeline

Keep a separate **AuditHero - Uploaded Files Audit Pipeline** for cases where the files already use AuditHero canonical columns and therefore need no mapping/conversion.

If an administrator uses the optional automated deployer, these pipelines are created automatically with the same names/defaults.

## 7. Build the reporting layer

Run **AuditHero - Build BI** after Setup has created the stable Gold/current tables. This creates or refreshes the Direct Lake semantic model and AuditHero Power BI report.

## 8. Test the complete operator workflow

Upload one small known payroll period under:

`AuditHero_Lakehouse / Files / import / raw`

Then:

1. run **AuditHero - Build Source Mapping Workbook**;
2. download/open `source_mapping_draft.xlsx`;
3. confirm/correct the field matches and save it as `source_mapping.xlsx`;
4. upload the approved mapping;
5. run **AuditHero - Convert Mapped Files and Run Audit** for the known date range; and
6. review the result in Power BI.

Only expand to a historical range after representative calculations have been validated.

## Optional Employment Hero API

If API automation is enabled later, store the required credentials in Azure Key Vault and grant the Fabric execution identity only the required secret-read access. See [Administration](ADMINISTRATION.md).

## Upgrading AuditHero

When upgrading to an approved AuditHero version:

1. update the package/Environment and notebook/pipeline definitions from the approved repository version;
2. publish the Environment;
3. run Setup;
4. run Self Test; and
5. validate one known payroll period before relying on changed results.

For automated deployments, see [CLI and automation](CLI_AND_AUTOMATION.md).
