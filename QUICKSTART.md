# AuditHero quickstart

Choose **Microsoft Fabric** or **Databricks**. Both run the same SCHADS calculation engine and effective-dated rule library.

## Microsoft Fabric

Prerequisites: Fabric workspace/capacity, Azure CLI or `FABRIC_ACCESS_TOKEN`, an Azure Key Vault and Employment Hero API credentials.

### 1. Configure the deployment

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
# edit workspace_id, workspace_name and key_vault_url
az login
```

### 2. Put Employment Hero credentials in Key Vault

Linux/macOS/WSL:

```bash
./fabric/scripts/configure_key_vault.sh
python fabric/scripts/preflight.py --check-secrets
```

Windows PowerShell:

```powershell
.\fabric\scripts\configure_key_vault.ps1
python fabric\scripts\preflight.py --check-secrets
```

The helper stores the canonical Employment Hero secret names in Key Vault without writing the values into Git or `fabric.json`. The Fabric notebook execution identity must also have Key Vault secret-read permission.

### 3. Deploy

```bash
./fabric/scripts/deploy.sh
```

or on Windows:

```powershell
.\fabric\scripts\deploy.ps1
```

The deployment entrypoint first runs the repository release validator and Fabric workspace/configuration preflight. It then creates/updates the schema-enabled Lakehouse, Runtime 2.0 Environment, pinned AuditHero wheel/runtime dependencies, parameterized notebooks, historical/monthly pipelines, disabled monthly schedule, stable `gold.current_*` Direct Lake snapshots, semantic model and Power BI report. Setup and Fabric-native regression self-tests run automatically unless disabled explicitly in `fabric.json`.

Fabric setup also creates empty controlled-register files in the Lakehouse. Populate the registers that apply to the historical population, run the Employment Hero connection/readiness notebooks, and validate one known pay period before using a multi-year remediation total or enabling the schedule.

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

The deployment script runs the same repository release validator before `databricks bundle validate`, deploys the bundle, and executes the Databricks-native self-test.

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

Replace example rows with controlled evidence. For a historical remediation audit, `industrial_instrument_history.csv` is a release gate because an employee classification by itself does not establish Award coverage. Part-time pattern history is also required where part-time employment exists. Optional event registers may remain empty only after confirming the event type was not applicable in the audit window.

Then:

```bash
databricks bundle run connection_test
databricks bundle run audit_readiness

databricks bundle run historical_audit -- \
  --start_date=2026-07-01 \
  --end_date=2026-07-31 \
  --actual_pay_source=PAYROLL_API
```

After manual validation, run the full period, for example:

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

Finally unpause the monthly job only after the validation run reconciles.

## Local release validation

For a development/release checkout:

```bash
pip install -e ".[dev]" build
python scripts/validate_repo.py --with-pytest --build-wheel
```

This compiles all Python, parses JSON/YAML, validates the SCHADS manifest/packs, checks Fabric/Databricks stage parity and safety defaults, runs pytest and builds the wheel.

## Common release gate

Do not use headline remediation totals until `REQUIRES_REVIEW` items, classifications, industrial instruments, work locations/public holidays and payroll-category mappings have been resolved and representative cases agree with manual calculations.
