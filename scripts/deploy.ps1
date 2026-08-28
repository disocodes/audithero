param(
  [string]$Target = "dev"
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($env:DATABRICKS_BUNDLE_VAR_sql_warehouse_id)) {
  throw "Set DATABRICKS_BUNDLE_VAR_sql_warehouse_id before deployment."
}
if (-not (Get-Command databricks -ErrorAction SilentlyContinue)) {
  throw "Databricks CLI is required."
}

Write-Host "Creating safe empty tenant configuration files where missing..."
python (Join-Path $Root "scripts\bootstrap_config.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running repository preflight..."
python (Join-Path $Root "scripts\validate_repo.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running Databricks authentication/warehouse preflight..."
python (Join-Path $Root "scripts\databricks_preflight.py") --target $Target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Validating Databricks bundle..."
databricks bundle validate -t $Target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Deploying AuditHero..."
databricks bundle deploy -t $Target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running workspace setup..."
databricks bundle run -t $Target setup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running Databricks-native regression checks..."
databricks bundle run -t $Target self_test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "AuditHero deployed and self-tested."
Write-Host "NEXT:"
Write-Host "1. .\scripts\configure_secrets.ps1"
Write-Host "2. databricks bundle run -t $Target connection_test"
Write-Host "3. databricks bundle run -t $Target audit_readiness"
Write-Host "4. Populate local config mappings/control registers identified by readiness."
Write-Host "5. .\scripts\sync_config.ps1 -Target $Target"
Write-Host "6. Rerun audit_readiness until blocking findings are resolved."
Write-Host "7. Run a one-month historical validation sample."
Write-Host "8. Only then run the full multi-year audit and enable the monthly schedule."
Write-Host "The monthly job remains PAUSED until you explicitly enable it."
