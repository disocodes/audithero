# Install AuditHero in Databricks

AuditHero includes a Databricks Declarative Automation Bundle (`databricks.yml`). Databricks can deploy bundles from the workspace UI, so a local CLI is not required for the normal installation path.

## Before you begin

You need:

- a Databricks workspace with Unity Catalog;
- permission to use Git folders and deploy bundle resources;
- a SQL warehouse for the AI/BI dashboard; and
- access to the AuditHero GitHub repository.

Employment Hero credentials are optional.

## 1. Add the repository as a Git folder

In the Databricks workspace:

1. open **Workspace**;
2. create a **Git folder**;
3. select GitHub as the provider;
4. use the AuditHero repository URL;
5. select the required branch/version.

Databricks detects `databricks.yml` at the repository root and exposes the bundle deployment UI.

## 2. Configure the deployment target

Open the bundle/Deployments view. Select the target (normally `dev` for validation, then a controlled production target when ready).

Set any required bundle variables through your organisation's approved configuration process, including the SQL warehouse used by the dashboard.

## 3. Deploy from the UI

Choose **Deploy**. The bundle creates the AuditHero jobs and AI/BI dashboard resources.

After deployment, open **Jobs & Pipelines**. The main jobs should include:

- AuditHero - Setup
- AuditHero - Self Test
- AuditHero - Build Source Mapping Workbook
- AuditHero - Convert Source Files
- AuditHero - File Readiness
- AuditHero - Audit Uploaded CSV Excel

Optional API jobs are clearly labelled `(Optional API)`.

## 4. Run Setup and Self Test

Run **AuditHero - Setup**, then **AuditHero - Self Test** from Jobs & Pipelines.

Setup creates/updates the Unity Catalog schemas/tables used by AuditHero. Self Test runs representative rule calculations. Do not move to production data if Self Test fails.

## 5. Confirm the Volume folders

The standard locations are:

`/Volumes/schads_payroll/bronze/landing/import/raw`

for original source exports, and:

`/Volumes/schads_payroll/bronze/landing/input`

for converted/canonical AuditHero files.

Use **Catalog Explorer** to upload files; operators do not need to use the CLI.

## 6. Test the complete file workflow

Upload one known payroll period and run from Jobs & Pipelines:

1. **AuditHero - Build Source Mapping Workbook**;
2. edit/download/upload the approved `source_mapping.xlsx`;
3. **AuditHero - Convert Source Files**;
4. **AuditHero - Audit Uploaded CSV Excel** with your start/end dates; and
5. review **AuditHero Payroll Compliance** in AI/BI.

## Optional Employment Hero API

If you enable API mode later, create the required Databricks secrets and run the optional Connection Test and API Readiness jobs. File-based auditing remains available regardless of API configuration.

## Upgrading

Pull/update the Git folder to the approved AuditHero version, use the Deployments UI to redeploy, then rerun Setup and Self Test. Validate a known payroll period before relying on changed results.

The CLI equivalent is documented separately in [CLI and automation](CLI_AND_AUTOMATION.md).
