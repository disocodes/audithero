# Fabric security

## Secrets

Employment Hero credentials belong in Azure Key Vault. The Lakehouse contains configuration/mapping evidence, not API secrets.

## Workspace roles

Separate:

- deployment/data engineering administrators;
- payroll/IR reviewers;
- report consumers.

Payroll report consumers normally need Power BI/semantic-model access, not edit rights to notebooks or control registers.

## Lakehouse controls

Restrict write access to `Files/config`, `ref`, `gold` and `ops`. Raw/silver payroll data contains sensitive employee information and should not be broadly discoverable.

## Service principal

For automated deployment, use a dedicated Entra application/service principal with only the Fabric workspace and Key Vault permissions required. Do not reuse an administrator's interactive identity for scheduled production operation.

## Evidence

Retain `audit_run_id`, calculation evidence, effective rule-pack source metadata, mappings/control-register references and remediation decisions according to payroll/legal/privacy requirements.