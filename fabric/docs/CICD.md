# Fabric CI/CD

The canonical source is this Git repository.

## Development

- rule changes: update effective-dated JSON + regression tests;
- shared payroll logic: update `src/schads_audit` + tests;
- Fabric-specific deployment/runtime: update `fabric/`;
- Databricks-specific deployment/runtime: update bundle/notebooks/resources.

## Fabric release

`fabric/scripts/deploy_fabric.py` uses Fabric REST definitions to create/update the workspace items. The Environment contains a wheel built from the checked-out commit, including the same SCHADS JSON packs used by Databricks.

The deployer records a deployment manifest in the Lakehouse so operators can identify the application/rule version used.

## Promotion

Use separate Fabric workspaces for dev/test/prod. Deploy the same Git commit to each workspace with different `fabric.json` files and Key Vaults. Do not edit production notebooks or rule files directly in the Fabric UI and leave them divergent from Git.

A production promotion should require:

1. Python regression suite pass;
2. Fabric runtime self-test pass;
3. one known-pay-period validation when Award rules materially change;
4. approval of new rule-pack source/effective date.