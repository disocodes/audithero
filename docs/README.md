# AuditHero documentation

Use this page to find the guide that matches what you are trying to do.

## Install, upgrade or remove AuditHero

AuditHero uses a single bootstrap notebook for the first installation on each platform. The installer creates the application resources and runs Setup and Self Test automatically. It also installs permanent **Install or Upgrade** and **Uninstall** notebooks inside the platform for later administration.

- [Microsoft Fabric installation, upgrade and removal](INSTALL_FABRIC_UI.md)
- [Databricks installation, upgrade and removal](INSTALL_DATABRICKS_UI.md)

A normal uninstall preserves payroll/audit storage. Permanent data deletion requires an explicit confirmation inside the uninstaller notebook.

## Payroll and audit operators

Start here if you upload data, run audits and review results.

1. [Quick start](../QUICKSTART.md)
2. [Importing and mapping CSV/Excel files](IMPORT_AND_FIELD_MAPPING.md)
3. [Audit data requirements](AUDIT_DATA_REQUIREMENTS.md)
4. [Running audits](RUNNING_AUDITS.md)
5. [Understanding results](UNDERSTANDING_RESULTS.md)
6. [Troubleshooting](TROUBLESHOOTING.md)

## Platform and payroll-system administrators

Use these guides to maintain an installed AuditHero environment.

- [Administration and security](ADMINISTRATION.md)
- [Notebook reference](NOTEBOOK_REFERENCE.md)
- [Optional CLI and automation](CLI_AND_AUTOMATION.md)
- [Architecture](ARCHITECTURE.md)

## Payroll governance and compliance reviewers

Use these guides when validating the basis of an audit.

- [SCHADS rules and evidence](SCHADS_RULES_AND_EVIDENCE.md)
- [Audit data requirements](AUDIT_DATA_REQUIREMENTS.md)
- [Understanding results](UNDERSTANDING_RESULTS.md)

The main guides are organised around user tasks. Implementation details that are not needed for installation, operation or audit review are kept in the technical and administration material.