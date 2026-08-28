param(
  [string]$Config = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Config) { $Config = Join-Path $Root "fabric\config\fabric.json" }
if (-not (Test-Path $Config)) {
  throw "Missing $Config. Copy fabric/config/fabric.example.json to fabric/config/fabric.json and configure it."
}

python -m pip install --quiet "requests>=2.32" "build>=1.2" "pyyaml>=6" "jsonschema>=4"

Write-Host "Running repository preflight..."
python (Join-Path $Root "scripts\validate_repo.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running Fabric configuration preflight..."
python (Join-Path $Root "fabric\scripts\preflight.py") --config $Config
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Deploying AuditHero to Microsoft Fabric..."
python (Join-Path $Root "fabric\scripts\deploy_fabric.py") --config $Config
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
