# AuditHero — SCHADS payroll compliance

AuditHero is a production-oriented payroll audit system for the **Social, Community, Home Care and Disability Services Industry Award (SCHADS / MA000100)**. It connects to Employment Hero, reconstructs historical Award entitlements with effective-dated rules, reconciles expected versus actual payroll and supports both ongoing payroll assurance and multi-year remediation audits.

The repository ships **two first-class deployments**:

- **Microsoft Fabric** — schema-enabled Lakehouse, Runtime Environment, Fabric notebooks, Data Factory pipelines, monthly schedule, Direct Lake semantic model and Power BI report.
- **Databricks** — Unity Catalog/Delta, notebooks, Declarative Automation Bundle jobs, monthly schedule and Databricks AI/BI dashboard.

Both platforms use the **same `schads_audit` Python engine and the same source-controlled `rules/MA000100` JSON library**. Platform services differ; payroll calculations do not.

## Shared calculation coverage

The engine covers effective-dated SACS and Home Care disability-care rates, classification/employment history, casual loading, weekends/public holidays/shiftwork, minimum engagement, roster and period overtime, broken shifts, sleepovers, part-time written patterns, rest-after-overtime, meal events, on-call/recall/remote/higher-duty events, TOIL, industrial-instrument history and actual-versus-expected pay-period reconciliation. Ambiguous or incomplete evidence produces `REQUIRES_REVIEW` rather than a guessed result.

## Microsoft Fabric

Use Fabric when Power BI and the Microsoft data platform are the preferred operating surface.

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
# edit workspace_id and key_vault_url
./fabric/scripts/deploy.sh
```

The installer creates/updates the Lakehouse, Runtime 2.0 Environment, AuditHero wheel, bound notebooks, historical/monthly Data Factory pipelines, disabled-by-default monthly schedule, Direct Lake semantic model and Power BI report. Employment Hero credentials remain in Azure Key Vault.

See `fabric/docs/DEPLOYMENT.md`.

## Databricks

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
./scripts/deploy.sh
./scripts/configure_secrets.sh
```

The bundle deploys setup/self-test/readiness jobs, canonical historical/monthly jobs and the Databricks AI/BI dashboard. The monthly schedule starts paused.

See `QUICKSTART.md` and `databricks/README.md`.

## Safe operating sequence

```text
Deploy -> self-test -> configure secrets -> connection test -> readiness review
       -> validate one known pay period -> run historical audit
       -> resolve REQUIRES_REVIEW -> enable monthly payroll workflow
```

## Rule source of truth

`rules/MA000100/` contains effective-dated rate, condition and allowance packs. Add new Fair Work versions there, record the source, add regression tests and redeploy. Do not fork Award logic separately for Fabric and Databricks.

AuditHero is compliance-engineering software, not legal advice. Independently validate Award coverage, classifications, industrial-instrument history and representative calculations before remediation or recovery decisions.
