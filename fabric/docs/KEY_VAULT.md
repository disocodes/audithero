# Azure Key Vault configuration

AuditHero Fabric notebooks retrieve Employment Hero credentials with `notebookutils.credentials.getSecret()`.

Use these canonical secret names for the HR API:

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

The current AuditHero release deliberately uses this fixed naming contract so every notebook, pipeline and deployment environment resolves credentials consistently. If you need different names, change `FabricAuditConfig` as a controlled code change rather than putting secret-name aliases in ordinary deployment configuration.

Grant the Fabric identity that executes notebooks permission to read these Key Vault secrets. Do not copy secret values into the Lakehouse, notebook parameters, Git, deployment-state files or Power BI.
