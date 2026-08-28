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

Add Key Vault secrets per `fabric/docs/KEY_VAULT.md`, then run connection/readiness checks and validate one known payroll period before enabling the schedule. Fabric setup creates empty controlled-register files in the Lakehouse for you; populate the registers that apply to your historical population.

Full instructions: `fabric/docs/DEPLOYMENT.md`.

## Databricks

Prerequisites: Databricks workspace with Unity Catalog, CLI 0.283.0+, SQL warehouse and Employment Hero API access.

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
export DATABRICKS_BUNDLE_VAR_accounts_email="accounts-user@your-company.example"
./scripts/deploy.sh
./scripts/configure_secrets.sh
```

Create tenant mappings and controlled registers from the version-controlled examples:

```bash
cp config/classification_mapping.example.json config/classification_mapping.json
cp config/work_type_mapping.example.json config/work_type_mapping.json
cp config/work_location_state_mapping.example.json config/work_location_state_mapping.json
cp config/employee_overrides.example.json config/employee_overrides.json
cp config/pay_category_mapping.example.json config/pay_category_mapping.json
cp config/public_holiday_overrides.example.csv config/public_holiday_overrides.csv
cp config/industrial_instrument_history.example.csv config/industrial_instrument_history.csv
cp config/part_time_patterns.example.csv config/part_time_patterns.csv
cp config/part_time_variations.example.csv config/part_time_variations.csv
cp config/overtime_rest_controls.example.csv config/overtime_rest_controls.csv
cp config/meal_break_events.example.csv config/meal_break_events.csv
cp config/supplemental_events.example.csv config/supplemental_events.csv
cp config/toil_register.example.csv config/toil_register.csv
```

Replace example rows with your controlled evidence. For a historical remediation audit, `industrial_instrument_history.csv` is a release gate because an employee classification by itself does not establish Award coverage. Part-time pattern history is also required where part-time employment exists. Optional event registers may remain empty only after confirming the event type was not applicable in the audit window.

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
