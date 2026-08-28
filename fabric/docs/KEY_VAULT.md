# Azure Key Vault configuration

AuditHero Fabric notebooks retrieve Employment Hero credentials with `notebookutils.credentials.getSecret()`.

Required HR secrets (default names):

```text
EH-ORGANISATION-ID
EH-HR-CLIENT-ID
EH-HR-CLIENT-SECRET
EH-HR-REFRESH-TOKEN
```

Optional Employment Hero Payroll secrets:

```text
EH-PAYROLL-API-KEY
EH-PAYROLL-BUSINESS-ID
```

Grant the Fabric identity used to execute notebooks permission to read these secrets. Do not copy secret values into the Lakehouse, notebook parameters, Git or Power BI.

The names can be changed in `fabric/config/fabric.json`; the Fabric config object passes them to the runtime.