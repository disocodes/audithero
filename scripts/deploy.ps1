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

Write-Host "Installing offline preflight dependency..."
python -m pip install --quiet "pyyaml>=6.0"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running AuditHero offline preflight..."
python (Join-Path $Root "scripts\preflight.py") --platform databricks
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Validating bundle..."
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
Write-Host "FILES mode requires no Employment Hero credentials."
Write-Host "Optional API mode: run .\scripts\configure_secrets.ps1, then connection_test and audit_readiness."
Write-Host "The monthly API job remains PAUSED until explicitly enabled."
