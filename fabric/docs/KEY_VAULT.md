# Azure Key Vault configuration

AuditHero Fabric notebooks retrieve Employment Hero credentials with `notebookutils.credentials.getSecret()`.

## Canonical secret names

HR API:

```text
EH-ORGANISATION-ID
EH-HR-CLIENT-ID
EH-HR-CLIENT-SECRET
EH-HR-REFRESH-TOKEN
```

Employment Hero Payroll actual-pay reconciliation:

```text
EH-PAYROLL-API-KEY
EH-PAYROLL-BUSINESS-ID
```

The current AuditHero release deliberately uses this fixed naming contract so every notebook, pipeline and deployment environment resolves credentials consistently. If different names are required, change `FabricAuditConfig` as a controlled code change rather than adding aliases to ordinary deployment configuration.

## Guided setup

Linux/macOS/WSL:

```bash
./fabric/scripts/configure_key_vault.sh
```

Windows PowerShell:

```powershell
.\fabric\scripts\configure_key_vault.ps1
```

Both scripts read the vault URL from `fabric/config/fabric.json`, prompt without echoing secret values, and write the values directly through Azure CLI. They do not persist the values locally.

To check that the secrets exist and are readable by the **current Azure CLI identity**:

```bash
python fabric/scripts/preflight.py --config fabric/config/fabric.json --check-secrets
```

## Fabric execution identity

The identity executing the Fabric notebooks must independently have permission to read the Key Vault secrets. A deployment operator being able to read a secret does not prove the notebook identity can read it. The **AuditHero - Employment Hero Connection** notebook is the authoritative post-deployment check.

Do not copy secret values into the Lakehouse, notebook parameters, Git, deployment-state files, pipeline definitions or Power BI.
