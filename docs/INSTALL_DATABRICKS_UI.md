# Install AuditHero in Databricks

AuditHero includes a Databricks Declarative Automation Bundle (`databricks.yml`). The intended installation and operating experience is through the Databricks workspace UI. Local CLI deployment remains available as an optional administrator method.

## Before you begin

You need:

- a Databricks workspace with Unity Catalog;
- permission to create/use a Git folder and deploy bundle resources;
- a SQL warehouse for the AI/BI dashboard; and
- access to the AuditHero GitHub repository.

Employment Hero credentials are **not** required for file-based auditing.

## 1. Add AuditHero as a Git folder

In the Databricks workspace:

1. open **Workspace**;
2. create a **Git folder**;
3. select GitHub as the provider;
4. enter the AuditHero repository URL; and
5. select the approved branch/version.

The repository contains `databricks.yml`, which defines the AuditHero jobs and dashboard resources.

## 2. Open the bundle deployment view

Open the bundle/Deployments experience for the Git folder and choose the required target. Use a validation/non-production target first where your governance process requires it.

Configure required bundle variables in the UI/approved workspace configuration, particularly the SQL warehouse used by the dashboard.

## 3. Deploy from the Databricks UI

Choose **Deploy**.

After deployment, open **Jobs & Pipelines**. You should see operator jobs including:

- **AuditHero - Build Source Mapping Workbook**
- **AuditHero - Convert Source Files**
- **AuditHero - Convert Mapped Files and Run Audit**
- **AuditHero - File Readiness**
- **AuditHero - Audit Uploaded CSV Excel**

You will also see:

- AuditHero - Setup
- AuditHero - Self Test

and optional Employment Hero API jobs that are clearly labelled `(Optional API)`.

## 4. Run Setup and Self Test

Run **AuditHero - Setup**, then **AuditHero - Self Test**.

Setup creates/updates the Unity Catalog schemas, reference tables and output tables used by the application. Self Test runs representative calculations against the installed rule library.

Do not proceed with production payroll evidence if Self Test fails.

## 5. Confirm the standard Volume folders

Raw exports are normally uploaded to:

`/Volumes/schads_payroll/bronze/landing/import/raw`

The mapping/conversion workflow writes canonical inputs to:

`/Volumes/schads_payroll/bronze/landing/input`

Use **Catalog Explorer** to upload/download files. Payroll operators do not need to use a terminal.

## 6. Configure your source fields

Upload one representative set of the original payroll/HR/timekeeping exports to the raw folder.

Run:

**AuditHero - Build Source Mapping Workbook**

Download `source_mapping_draft.xlsx`, review the suggested field matches, then upload the approved file as:

`source_mapping.xlsx`

The mapping workbook is the normal place to tell AuditHero that, for example, `Employee Number` means `employee_id` or `Clock In` means `start_datetime`.

See [Import and field mapping](IMPORT_AND_FIELD_MAPPING.md).

## 7. Run the complete mapped-import audit

From **Jobs & Pipelines**, run:

**AuditHero - Convert Mapped Files and Run Audit**

Set the audit start/end dates and use the standard source/mapping/output paths unless your administrator intentionally changed them.

The job then performs conversion, readiness, payroll audit and AI/BI refresh in sequence.

For the first run, use one known payroll period that can be checked manually before expanding to a historical range.

## 8. Open the dashboard

Open the AuditHero payroll compliance dashboard in Databricks AI/BI. Review confirmed exceptions separately from `REQUIRES_REVIEW` items.

See [Understanding results](UNDERSTANDING_RESULTS.md).

## Optional Employment Hero API

If API automation is required later, create the required Databricks secrets and run the optional Connection Test and API Readiness jobs. File-based auditing continues to work regardless of API configuration.

## Upgrading AuditHero

1. update/pull the Git folder to the approved AuditHero version;
2. use the bundle deployment UI to redeploy;
3. run Setup;
4. run Self Test; and
5. validate one known payroll period before relying on changed calculations or mappings.

The optional command-line equivalent is documented in [CLI and automation](CLI_AND_AUTOMATION.md).
