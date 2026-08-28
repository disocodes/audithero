# Azure Key Vault configuration

Azure Key Vault is **optional** in AuditHero. It is needed only when you choose Employment Hero API ingestion.

For credential-free CSV/XLSX auditing, leave `key_vault_url` blank in `fabric/config/fabric.json`, upload your workbook/files to the Lakehouse, and run `AuditHero - Uploaded Files Audit Pipeline`.

If you enable Employment Hero API mode, Fabric notebooks retrieve credentials with `notebookutils.credentials.getSecret()` using these canonical secret names:

```text
EH-ORGANISATION-ID
EH-HR-CLIENT-ID
EH-HR-CLIENT-SECRET
EH-HR-REFRESH-TOKEN
```

For Employment Hero Payroll actual-pay reconciliation, also configure:

```text
EH-PAYROLL-API-KEY
EH-PAYROLL-BUSINESS-ID
```

The current AuditHero release deliberately uses this fixed naming contract so every API notebook and pipeline resolves credentials consistently. If you need different names, change `FabricAuditConfig` as a controlled code change.

Grant the Fabric identity that executes API notebooks permission to read these Key Vault secrets. Do not copy secret values into the Lakehouse, notebook parameters, Git, deployment-state files or Power BI.
