# Databricks vs Microsoft Fabric

Both are production targets. Choose based on the operating environment, not payroll arithmetic.

## Prefer Fabric when

- Payroll/Accounts already lives in Microsoft 365/Power BI.
- You want Direct Lake + Power BI as the primary user experience.
- A single Fabric workspace/capacity is operationally simpler.
- Azure Key Vault and Microsoft identity/governance are preferred.

## Prefer Databricks when

- The audit engine will become a broader multi-employer/multi-award data product.
- Data engineering/CI/CD/ML workloads dominate.
- Unity Catalog/Lakeflow are already strategic infrastructure.
- Databricks AI/BI is sufficient for the consumer interface.

## Important

Do not run different Award logic on the two platforms. `src/schads_audit` and `rules/MA000100` are the canonical calculation assets. Platform-specific modules handle storage, secrets, scheduling and BI only.