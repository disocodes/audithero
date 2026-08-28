# AuditHero on Microsoft Fabric

This directory is a **complete Microsoft Fabric deployment**, not a compatibility shim.

Read in this order:

1. `DEPLOYMENT.md` — create the Fabric application.
2. `KEY_VAULT.md` — Employment Hero secrets.
3. `EMPLOYMENT_HERO.md` — tenant mapping and connectivity.
4. `HISTORICAL_AUDIT.md` — multi-year audits.
5. `MONTHLY_PAYROLL.md` — recurring payroll workflow.
6. `POWER_BI.md` — Direct Lake semantic model/report.
7. `CONTROL_REGISTERS.md` — part-time patterns, TOIL, EA/IFA and other evidence.
8. `SECURITY.md` — permissions and data controls.
9. `CICD.md` — source control/deployment strategy.

The Fabric stack uses the same packaged `schads_audit` calculation engine and rule packs as Databricks.