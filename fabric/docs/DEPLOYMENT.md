# Fabric deployment

## Prerequisites

Required:

- Microsoft Fabric capacity and a workspace where you can create Lakehouses, Environments, Notebooks, Data Pipelines, semantic models and reports.
- Azure CLI authenticated to the tenant containing the Fabric workspace, or `FABRIC_ACCESS_TOKEN`.
- Python 3.11+ on the deployment machine.

Optional:

- Azure Key Vault and Employment Hero credentials, only if you want direct API ingestion.

A complete CSV/XLSX audit can be deployed and run without Employment Hero credentials.

## Configure

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
```

For file-only mode set only the workspace information you need, especially:

```json
{
  "workspace_id": "<workspace-guid>",
  "key_vault_url": ""
}
```

The default file input folder is:

```text
/lakehouse/default/Files/input
```

Do not put Employment Hero secrets in `fabric.json`.

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
3. AuditHero wheel and SCHADS rule library;
4. Environment publication;
5. setup/self-test notebooks;
6. file-readiness notebook;
7. uploaded CSV/XLSX audit notebook;
8. `AuditHero - Uploaded Files Audit Pipeline`;
9. optional Employment Hero connection/readiness/historical/monthly notebooks and pipelines;
10. disabled monthly API schedule;
11. Direct Lake semantic model and Power BI report;
12. stable `gold.current_*` tables that are replaced only after a successful audit.

## File-only workflow — no Employment Hero credentials

Generate a workbook if helpful:

```bash
pip install -e .
python tools/build_input_workbook.py --output audithero_input.xlsx
```

Upload it in Fabric to:

```text
AuditHero_Lakehouse
  Files
    input
      audithero_input.xlsx
```

You can instead upload separate CSV/XLSX files such as `employees.csv`, `timesheets.xlsx`, etc.

Run:

```text
AuditHero - Uploaded Files Audit Pipeline
```

The pipeline executes:

```text
Validate Uploaded Files
        ↓
Audit Uploaded Files
        ↓
Refresh Direct Lake and Power BI
```

The file-readiness step validates required sheets/files, columns, classification coverage, pay-period information and historical control registers before the audit is allowed to proceed.

## Optional Employment Hero API workflow

If you later want automatic extraction:

1. create/configure Azure Key Vault;
2. add the six Employment Hero secrets documented in `KEY_VAULT.md`;
3. set `key_vault_url` in `fabric.json`;
4. rerun `./fabric/scripts/deploy.sh`;
5. run the Employment Hero connection test;
6. run API readiness;
7. use the historical/monthly API pipelines.

## Historical control files

Fabric setup creates the control area under:

```text
Files/config
```

For remediation work, populate the applicable registers, especially:

- `industrial_instrument_history.csv`
- `part_time_patterns.csv` where part-time employment exists
- `public_holiday_overrides.csv` where local/substituted holidays matter
- `meal_break_events.csv`
- `overtime_rest_controls.csv`
- `supplemental_events.csv`
- `toil_register.csv`

## Recommended sequence

1. Deploy.
2. Confirm self-test passes.
3. Upload one known payroll period.
4. Run `AuditHero - Uploaded Files Audit Pipeline`.
5. Compare representative employees manually.
6. Resolve `REQUIRES_REVIEW` items and historical coverage evidence.
7. Run the full historical range.
8. Review Power BI.
9. Optionally configure Employment Hero API ingestion.
10. Enable recurring monthly automation only after validation.

A successful infrastructure deployment is not the same as payroll validation.
