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

### 1. Deploy the application

Linux/macOS/WSL:

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
export DATABRICKS_BUNDLE_VAR_accounts_email="accounts-user@your-company.example"
./scripts/deploy.sh
```

Windows PowerShell:

```powershell
databricks auth login --host https://<workspace>
$env:DATABRICKS_BUNDLE_VAR_sql_warehouse_id = "<warehouse-id>"
$env:DATABRICKS_BUNDLE_VAR_accounts_email = "accounts-user@your-company.example"
.\scripts\deploy.ps1
```

The deployment script first creates **safe active tenant config files** where missing: JSON mappings are `{}` and CSV registers contain headers only. It never copies example/sample rows into active evidence. These active files are gitignored but explicitly included by the Databricks bundle sync configuration. The script then runs repository + Databricks preflights, bundle validation/deployment, workspace setup and the Databricks-native self-test.

### 2. Configure Employment Hero secrets

Linux/macOS/WSL:

```bash
./scripts/configure_secrets.sh
```

Windows PowerShell:

```powershell
.\scripts\configure_secrets.ps1
```

### 3. Discover the tenant and run readiness

```bash
databricks bundle run connection_test
databricks bundle run audit_readiness
```

Readiness identifies missing classification/pay-category/location mappings and controlled evidence. It now verifies **employee-level register coverage**: a sample row or unrelated employee cannot satisfy the industrial-instrument or part-time-pattern release gate.

Use the `config/*.example.*` files only as **schema/examples** while editing the already-created active files. Do not copy their sample rows wholesale.

For historical remediation:

- `industrial_instrument_history.csv` must have controlled evidence for every employee in the population;
- `part_time_patterns.csv` must cover every employee who is or was part-time;
- optional event registers may remain empty only after confirming that event type was not applicable in the audit window.

### 4. Sync tenant configuration

After editing the local gitignored `config/*.json` and controlled CSV files:

Linux/macOS/WSL:

```bash
./scripts/sync_config.sh dev
```

Windows PowerShell:

```powershell
.\scripts\sync_config.ps1 -Target dev
```

Then rerun:

```bash
databricks bundle run audit_readiness
```

Repeat edit → sync → readiness until blocking findings are resolved.

### 5. Validate one known period

```bash
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
