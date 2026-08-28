# AuditHero quickstart

Choose **Microsoft Fabric** or **Databricks**. Both run the same SCHADS engine.

## Microsoft Fabric

Prerequisites: Fabric workspace/capacity, Azure CLI or `FABRIC_ACCESS_TOKEN`, Azure Key Vault and Employment Hero API credentials.

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
# set workspace_id and key_vault_url
az login
./fabric/scripts/deploy.sh
```

The installer creates the Lakehouse, Runtime 2.0 Environment, custom wheel, notebooks, historical/monthly pipelines, disabled monthly schedule, stable `gold.current_*` Direct Lake snapshots, semantic model and Power BI report.

Add Key Vault secrets per `fabric/docs/KEY_VAULT.md`, then run connection/readiness checks and validate one known payroll period before enabling the schedule. Full instructions: `fabric/docs/DEPLOYMENT.md`.

## Databricks

Prerequisites: Databricks workspace with Unity Catalog, CLI 0.283.0+, SQL warehouse and Employment Hero API access.

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
export DATABRICKS_BUNDLE_VAR_accounts_email="accounts-user@your-company.example"
./scripts/deploy.sh
./scripts/configure_secrets.sh
```

Then:

```bash
databricks bundle run connection_test
databricks bundle run audit_readiness

databricks bundle run historical_audit -- \
  --start_date=2026-07-01 \
  --end_date=2026-07-31 \
  --actual_pay_source=PAYROLL_API
```

After manual validation, run your full period, for example:

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

Finally unpause the monthly job only after the validation run reconciles.

## Common release gate

Do not use headline remediation totals until `REQUIRES_REVIEW` items, classifications, industrial instruments, work locations/public holidays and payroll-category mappings have been resolved and representative cases agree with manual calculations.
