# Optional CLI and automation

AuditHero can be installed and operated from the Fabric/Databricks UI. The commands in this guide are optional equivalents for administrators who prefer repeatable scripted deployment, CI/CD or disaster recovery.

## Microsoft Fabric automated deployment

Copy the example configuration, set the Fabric workspace ID and run the platform script.

Linux/macOS:

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
./fabric/scripts/deploy.sh
```

Windows PowerShell:

```powershell
Copy-Item fabric/config/fabric.example.json fabric/config/fabric.json
.\fabric\scripts\deploy.ps1
```

The automated Fabric installer creates/updates the core workspace items plus the uploaded-file and source-mapping pipelines. Key Vault configuration can remain blank if API mode is not used.

## Databricks CLI deployment

The UI bundle deployment is the normal installation option. The CLI equivalent is:

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
./scripts/deploy.sh
```

Only run the secrets helper if you are enabling optional API mode.

## Preflight

`scripts/preflight.py` performs repository/config structural checks before an automated deployment. It does not replace the platform-native Self Test or a known-period payroll validation.

## CI/CD

Use the same order in automated promotion:

1. repository tests/preflight;
2. deploy to non-production;
3. platform Setup/Self Test;
4. known-period audit regression;
5. approval; and
6. production promotion.

Do not automatically enable recurring schedules simply because infrastructure deployment succeeded.
