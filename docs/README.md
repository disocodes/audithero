# AuditHero documentation

Use this page to find the guide for the task being performed.

## Installation, upgrade and removal

- [Microsoft Fabric installation, upgrade and removal](INSTALL_FABRIC_UI.md)
- [Databricks installation, upgrade and removal](INSTALL_DATABRICKS_UI.md)

The first installation uses a platform-specific installer notebook. After installation, managed **Install or Upgrade** and **Uninstall** notebooks are available inside the target platform.

A standard uninstall preserves payroll and audit storage. Permanent data deletion requires explicit confirmation in the uninstaller notebook.

## Payroll and audit operators

Use these guides to prepare data, run audits and review results:

1. [Quick start](../QUICKSTART.md)
2. [Importing and mapping CSV/Excel files](IMPORT_AND_FIELD_MAPPING.md)
3. [Audit data requirements](AUDIT_DATA_REQUIREMENTS.md)
4. [Running audits](RUNNING_AUDITS.md)
5. [Understanding results](UNDERSTANDING_RESULTS.md)
6. [Troubleshooting](TROUBLESHOOTING.md)

## Administrators

Use these guides to maintain an installed AuditHero environment:

- [Administration and security](ADMINISTRATION.md)
- [Notebook reference](NOTEBOOK_REFERENCE.md)
- [CLI and automation](CLI_AND_AUTOMATION.md)
- [Architecture](ARCHITECTURE.md)

## Payroll governance and compliance review

Use these guides when validating the basis and limitations of an audit:

- [SCHADS rules and evidence](SCHADS_RULES_AND_EVIDENCE.md)
- [Audit data requirements](AUDIT_DATA_REQUIREMENTS.md)
- [Understanding results](UNDERSTANDING_RESULTS.md)

## Platform-specific entry points

### Microsoft Fabric

Routine operation uses the deployed Fabric pipelines and Power BI report.

### Databricks

Routine operation uses **Jobs & Pipelines**, **Catalog Explorer**, **AI/BI** and **Genie**. No separate AuditHero application is required.
