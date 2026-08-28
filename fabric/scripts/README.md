# Fabric deployment scripts

- `deploy_fabric.py` — idempotent Fabric REST deployer.
- `deploy.sh` — Linux/macOS entry point.
- `deploy.ps1` — Windows PowerShell entry point.
- `build_fabric_wheel.py` — builds the shared AuditHero wheel for the Fabric Environment.

The deployer authenticates with `FABRIC_ACCESS_TOKEN` or Azure CLI.