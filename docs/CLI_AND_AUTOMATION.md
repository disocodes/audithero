# Optional CLI and automation

AuditHero can be installed and operated from the Microsoft Fabric or Databricks UI. The commands in this guide are optional equivalents for administrators who prefer repeatable scripted deployment, CI/CD or disaster recovery.

Normal payroll/audit operators do not need these commands.

## Microsoft Fabric automated deployment

Copy the example configuration, set the Fabric workspace ID and run the platform script.

### Linux/macOS

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
./fabric/scripts/deploy.sh
```

### Windows PowerShell

```powershell
Copy-Item fabric/config/fabric.example.json fabric/config/fabric.json
.\fabric\scripts\deploy.ps1
```

The automated Fabric installer creates/updates the core workspace items, canonical uploaded-file path, source-mapping pipelines and **AuditHero - Convert Mapped Files and Run Audit**. Key Vault configuration may remain blank when Employment Hero API mode is not used.

## Databricks automated bundle deployment

UI bundle deployment is the normal installation option. The scripted equivalent is available on both major administration environments.

### Linux/macOS

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
./scripts/deploy.sh
```

### Windows PowerShell

```powershell
databricks auth login --host https://<workspace>
$env:DATABRICKS_BUNDLE_VAR_sql_warehouse_id = "<warehouse-id>"
.\scripts\deploy.ps1
```

The Databricks deployment validates the bundle, deploys the jobs/dashboard, runs Setup and executes the platform-native Self Test.

Only run `scripts/configure_secrets.sh` or `scripts/configure_secrets.ps1` if optional Employment Hero API mode is being enabled.

## Source mapping after scripted deployment

Scripted deployment does not change the normal payroll-operator workflow. After installation, users still work in the platform UI:

1. upload raw exports;
2. build/review `source_mapping.xlsx`;
3. run **AuditHero - Convert Mapped Files and Run Audit**; and
4. review the dashboard/report.

## Preflight

`scripts/preflight.py` performs repository/config structural checks before an automated deployment. It checks items such as Python/JSON/YAML structure, rule-manifest references and required cross-platform deployment entrypoints.

Preflight does not replace:

- the Fabric/Databricks native Self Test; or
- a manually validated known payroll period.

## CI/CD

Use the same controlled order for automated promotion:

1. repository tests and preflight;
2. build the package/artifacts;
3. deploy to a non-production workspace/target;
4. run platform Setup and Self Test;
5. run a known-period audit regression;
6. obtain the required approval; and
7. promote to production.

Do not automatically enable recurring payroll schedules merely because an infrastructure deployment succeeded.
