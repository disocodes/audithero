# Install AuditHero in Microsoft Fabric

This guide uses the Microsoft Fabric user interface as the main installation and operating surface. The CLI/REST installer remains available as an optional automation method; see [CLI and automation](CLI_AND_AUTOMATION.md).

## What the completed workspace contains

A complete AuditHero Fabric workspace contains:

- a schema-enabled Lakehouse named `AuditHero_Lakehouse`;
- an AuditHero Fabric Environment;
- setup and self-test notebooks;
- source mapping and file-conversion notebooks/pipelines;
- uploaded-file audit pipeline;
- optional Employment Hero API notebooks/pipelines;
- Direct Lake semantic model; and
- Power BI report.

## Before you begin

You need:

- a Fabric workspace on suitable capacity;
- permission to create Lakehouses, Environments, notebooks, pipelines, semantic models and reports; and
- the AuditHero repository available from GitHub.

Azure Key Vault is **not** required for uploaded-file audits. It is needed only if you enable optional Employment Hero API connectivity.

## UI-first installation approach

AuditHero is designed so normal operations stay in Fabric. For initial setup you can either sync/import the repository assets through Fabric's supported source-control/item-import features or have an administrator perform the automated deployment once. If your organisation does not allow CLI deployment, use the following UI sequence and keep the repository as the source of the notebook/config files.

### 1. Create or select the Fabric workspace

Create a workspace for AuditHero or select the workspace where payroll compliance data will live. Limit membership to the people who need access to payroll data.

### 2. Create the Lakehouse

In the workspace choose **New item → Lakehouse** and create:

`AuditHero_Lakehouse`

Use the Lakehouse as the default Lakehouse for AuditHero notebooks.

### 3. Create the Environment

Create an Environment called `AuditHero_Environment` and configure it using the versions in `fabric/environment/`.

The Environment needs the dependencies used by AuditHero, including pandas/requests/holidays, `openpyxl` for Excel mapping, and Semantic Link Labs for the BI deployment notebook. Publish the Environment after making changes.

For a controlled production installation, load the AuditHero package/wheel into this Environment rather than installing ad-hoc packages separately in each operator notebook.

### 4. Add the AuditHero notebooks

Import/create the notebooks from `fabric/notebooks/` and attach them to `AuditHero_Lakehouse` and `AuditHero_Environment`.

The normal operator-facing notebooks are:

- `AuditHero - Build Source Mapping Workbook`
- `AuditHero - Convert Source Files`
- `AuditHero - File Readiness`
- `AuditHero - Audit Uploaded CSV Excel`

Administrator/optional notebooks include Setup, Self Test, API Connection/Readiness, Historical API Audit, Monthly API Audit and Build BI.

The notebook source files contain explanations of each step so administrators can open a notebook and understand what it is doing without reading the Python package internals.

### 5. Run Setup and Self Test

Run Setup once. It creates the Lakehouse schemas and output tables and loads the rule-reference tables.

Then run Self Test. Do not continue if the self-test reports a failure.

### 6. Create the operator pipelines

Create Data Factory pipelines that call the corresponding notebooks:

**AuditHero - Build Source Mapping Workbook**

- `source_root` default: `/lakehouse/default/Files/import/raw`
- `draft_path` default: `/lakehouse/default/Files/import/source_mapping_draft.xlsx`
- `overwrite` default: `false`

**AuditHero - Convert Source Files**

- `source_root`: `/lakehouse/default/Files/import/raw`
- `mapping_path`: `/lakehouse/default/Files/import/source_mapping.xlsx`
- `output_root`: `/lakehouse/default/Files/input`
- `strict`: `true`

**AuditHero - Uploaded Files Audit Pipeline**

- input root: `/lakehouse/default/Files/input`
- expose start/end date parameters;
- run File Readiness before the audit notebook;
- refresh the BI layer only after a successful audit.

If your administrator uses the optional AuditHero deployment script, these pipelines are created automatically with the same names and defaults.

### 7. Build the reporting layer

Run `AuditHero - Build BI` after setup has created the stable `gold.current_*` tables. This creates/refreshes the Direct Lake semantic model and AuditHero Power BI report.

### 8. Test the operator path

Upload one small known payroll period to `Files/import/raw`, then run:

1. Build Source Mapping Workbook;
2. Convert Source Files;
3. Uploaded Files Audit Pipeline; and
4. Power BI review.

Do not enable recurring schedules until this end-to-end path is validated.

## Optional Employment Hero API

If you later enable API mode, store credentials in Azure Key Vault and grant the Fabric execution identity permission to read only the required secrets. See [Administration](ADMINISTRATION.md).

## Upgrading AuditHero

Keep the workspace connected to the repository/version-management process used by your organisation. After an upgrade:

1. update the AuditHero Environment/package and notebook/pipeline definitions;
2. publish the Environment;
3. run Setup (it is designed to be repeatable);
4. run Self Test;
5. validate one known period before relying on changed results.

For automated deployments, see [CLI and automation](CLI_AND_AUTOMATION.md).
