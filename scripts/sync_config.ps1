param(
  [string]$Target = "dev"
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

python (Join-Path $Root "scripts\bootstrap_config.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python (Join-Path $Root "scripts\validate_repo.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python (Join-Path $Root "scripts\databricks_preflight.py") --target $Target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Deploying updated gitignored tenant configuration to Databricks target '$Target'..."
databricks bundle deploy -t $Target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Tenant configuration synchronized."
Write-Host "NEXT: databricks bundle run -t $Target audit_readiness"
Write-Host "Repeat edit -> sync_config -> audit_readiness until blocking findings are resolved."
