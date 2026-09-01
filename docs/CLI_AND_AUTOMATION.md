# Optional CLI and automation

This guide is for administrators using scripted deployment, CI/CD or disaster-recovery procedures. The platform installer notebooks remain available for UI-based installation and upgrades.

## Microsoft Fabric automated deployment

The UI installer is `installers/Fabric_Install_AuditHero.py`. The scripted deployment path is:

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

The Fabric deployment creates or updates the core workspace items, uploaded-file workflow, source-mapping workflow and reporting layer. Key Vault configuration can remain blank when Employment Hero API mode is not used.

## Databricks automated bundle deployment

The UI installer is `installers/Databricks_Install_AuditHero.py`. The repository also provides a Databricks Declarative Automation Bundle.

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

The Databricks deployment validates and deploys the Bundle, runs Setup and executes Self Test. Setup creates the Unity Catalog data structures, governed metric views and AuditHero Genie configuration used by the deployed Jobs and AI/BI dashboard.

Run `scripts/configure_secrets.sh` or `scripts/configure_secrets.ps1` only when Employment Hero API mode is being enabled.

## Uploaded-file workflow after deployment

Installation method does not change the audit workflow:

1. upload raw source exports;
2. build and approve `source_mapping.xlsx` when required;
3. run **AuditHero - Convert Mapped Files and Run Audit**; and
4. review the platform reporting layer.

## Preflight

`scripts/preflight.py` performs repository and configuration structural checks before an automated deployment. It checks Python, JSON and YAML structure, rule-manifest references, installer notebooks and required cross-platform deployment entry points.

Preflight does not replace:

- the platform-native Setup and Self Test; or
- validation of a known payroll period.

## CI/CD

A controlled promotion sequence is:

1. run repository tests and preflight;
2. build the package and deployment artifacts;
3. deploy to a non-production workspace or target;
4. run platform Setup and Self Test;
5. run a known-period audit regression;
6. complete the required review/approval; and
7. promote the approved release to production.

Recurring payroll schedules should be enabled only after the deployed release and representative payroll results have been validated.
