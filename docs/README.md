# AuditHero documentation

Use this index to find the guide for the task being performed.

## Install, upgrade, or remove AuditHero

- [Microsoft Fabric installation, upgrade, and removal](INSTALL_FABRIC_UI.md)
- [Databricks installation, upgrade, and removal](INSTALL_DATABRICKS_UI.md)

The first installation uses the platform-specific installer notebook. After installation, managed **Install or Upgrade** and **Uninstall** notebooks are available inside the target platform.

A standard uninstall preserves payroll and audit storage. Permanent data deletion requires explicit confirmation in the uninstaller notebook.

## Prepare and run payroll audits

1. [Quick start](../QUICKSTART.md)
2. [Import and field mapping](IMPORT_AND_FIELD_MAPPING.md)
3. [Audit data requirements](AUDIT_DATA_REQUIREMENTS.md)
4. [Running audits](RUNNING_AUDITS.md)
5. [Understanding results](UNDERSTANDING_RESULTS.md)
6. [Troubleshooting](TROUBLESHOOTING.md)

## Administration and technical reference

- [Administration and security](ADMINISTRATION.md)
- [Notebook reference](NOTEBOOK_REFERENCE.md)
- [CLI and automation](CLI_AND_AUTOMATION.md)
- [Architecture](ARCHITECTURE.md)

## Payroll governance and evidence

- [SCHADS rules and evidence](SCHADS_RULES_AND_EVIDENCE.md)
- [Audit data requirements](AUDIT_DATA_REQUIREMENTS.md)
- [Understanding results](UNDERSTANDING_RESULTS.md)

## Platform operating surfaces

### Microsoft Fabric

Routine operation uses the deployed Fabric pipelines, AuditHero Lakehouse, and **AuditHero - SCHADS Payroll Compliance** Power BI report.

### Databricks

Routine operation uses **Jobs & Pipelines**, **Catalog Explorer**, the **AuditHero - SCHADS Payroll Compliance** AI/BI dashboard, and the **AuditHero - Payroll Compliance** Genie space.

> AuditHero is compliance-support software, not legal advice. Validate Award coverage, classifications, historical industrial instruments, source mappings, and representative calculations before using results for remediation, recovery, or payroll changes.
