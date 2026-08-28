# Fabric deployment

## Prerequisites

- Microsoft Fabric capacity and a workspace where you can create Lakehouses, Environments, Notebooks, Data Pipelines, semantic models and reports.
- Azure CLI authenticated to the tenant containing the Fabric workspace.
- Python 3.11+ on the deployment machine.
- Azure Key Vault for Employment Hero credentials.

## Configure

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
```

Set:

- `workspace_id`
- `lakehouse_name`
- `environment_name`
- `key_vault_url`
- monthly schedule/timezone

Do not put Employment Hero secrets in this file.

## Deploy

Linux/macOS:

```bash
./fabric/scripts/deploy.sh
```

Windows PowerShell:

```powershell
./fabric/scripts/deploy.ps1
```

The deployer is idempotent. It creates or updates:

1. schema-enabled AuditHero Lakehouse;
2. Fabric Runtime 2.0 Environment;
3. AuditHero wheel and custom-library configuration;
4. Environment publication;
5. Setup/self-test/connectivity/readiness/historical/monthly/BI notebooks;
6. notebook-to-Lakehouse/Environment bindings;
7. historical audit pipeline;
8. monthly payroll pipeline;
9. monthly schedule, initially disabled;
10. setup and self-test execution;
11. Direct Lake semantic model and Power BI report when output tables exist.

## After deployment

1. Put Employment Hero secrets in Key Vault.
2. Run the Employment Hero connection notebook/pipeline.
3. Run readiness analysis.
4. Fill mappings/control registers in `Files/config`.
5. Validate one known pay period.
6. Run the historical range.
7. Review Power BI.
8. Enable the monthly schedule only after validation.

The deployment must fail if setup/self-tests fail. A successful infrastructure deployment is not the same as payroll validation.