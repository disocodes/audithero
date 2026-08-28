# Fabric deployment

## Prerequisites

- Microsoft Fabric capacity and a workspace where you can create Lakehouses, Environments, Notebooks, Data Pipelines, semantic models and reports.
- Azure CLI authenticated to the tenant containing the Fabric workspace, or `FABRIC_ACCESS_TOKEN` for the Fabric REST deployment.
- Python 3.11+ on the deployment machine.
- Azure Key Vault for Employment Hero credentials.

## 1. Configure

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
```

Set at minimum:

- `workspace_id`
- `workspace_name`
- `lakehouse_name`
- `environment_name`
- `key_vault_url`
- monthly schedule/timezone
- historical default dates/pay source

Do not put Employment Hero secrets in this file. `fabric/config/fabric.json` is gitignored.

## 2. Configure Key Vault

Linux/macOS/WSL:

```bash
./fabric/scripts/configure_key_vault.sh
```

Windows PowerShell:

```powershell
.\fabric\scripts\configure_key_vault.ps1
```

The helper writes the canonical AuditHero Employment Hero secret names directly to Azure Key Vault. It does not store secret values in Git or the Fabric config file.

Grant the Fabric notebook execution identity permission to read those Key Vault secrets. See `KEY_VAULT.md`.

Optionally verify secret existence with the deployment identity:

```bash
python fabric/scripts/preflight.py --config fabric/config/fabric.json --check-secrets
```

This does not prove the notebook execution identity has access; the connection notebook verifies that after deployment.

## 3. Deploy

Linux/macOS/WSL:

```bash
./fabric/scripts/deploy.sh
```

Windows PowerShell:

```powershell
.\fabric\scripts\deploy.ps1
```

Before creating or updating Fabric items, the entrypoint runs:

1. `scripts/validate_repo.py` — Python/JSON/YAML/rule-library/parity/safety validation;
2. `fabric/scripts/preflight.py` — Fabric config, authentication and workspace visibility validation.

The deployer is idempotent. It then creates or updates:

1. schema-enabled AuditHero Lakehouse;
2. Fabric Runtime 2.0 Environment;
3. AuditHero wheel and pinned public libraries;
4. Environment publication;
5. Setup/self-test/connectivity/readiness/historical/monthly/BI notebooks;
6. notebook-to-Lakehouse/Environment bindings and real Fabric parameter cells;
7. historical audit pipeline;
8. monthly payroll pipeline;
9. monthly schedule, initially disabled;
10. setup and Fabric-native self-test execution;
11. Direct Lake semantic model and Power BI report.

The BI Environment pins `semantic-link-labs==0.17.0`. `06_build_bi.py` performs a runtime version/signature guard before modifying the semantic model or report, so unexpected dependency/API drift fails early.

## 4. Tenant validation

After deployment:

1. Run **AuditHero - Employment Hero Connection**.
2. Run **AuditHero - Readiness**.
3. Fill or verify mappings/control registers in `Files/config`.
4. Validate one known pay period against manual payroll calculations.
5. Resolve `REQUIRES_REVIEW` records.
6. Run the historical range.
7. Review the Direct Lake Power BI report.
8. Enable the monthly schedule only after sign-off.

The deployment must fail if setup/self-tests fail. A successful infrastructure deployment is not the same as payroll validation, Award coverage validation or legal sign-off.

## Local release validation

For maintainers or before promoting a new rules/engine revision:

```bash
pip install -e ".[dev]" build
python scripts/validate_repo.py --with-pytest --build-wheel
```
