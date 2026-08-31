param(
  [string]$Config = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Config) { $Config = Join-Path $Root "fabric\config\fabric.json" }
if (-not (Test-Path $Config)) {
  throw "Missing $Config. Copy fabric/config/fabric.example.json to fabric/config/fabric.json and configure workspace_id. Key Vault is optional for CSV/XLSX mode."
}
python -m pip install --quiet "requests>=2.32" "build>=1.2" "pyyaml>=6.0" "openpyxl>=3.1"
python (Join-Path $Root "scripts\preflight.py") --platform fabric --fabric-config $Config
python (Join-Path $Root "fabric\scripts\deploy_fabric.py") --config $Config
python (Join-Path $Root "fabric\scripts\deploy_file_source.py") --config $Config
python (Join-Path $Root "fabric\scripts\deploy_source_mapping.py") --config $Config
Write-Host ""
Write-Host "AuditHero Fabric deployment complete."
Write-Host "Normal UI workflow: upload raw exports -> Build Source Mapping Workbook -> approve source_mapping.xlsx -> Convert Mapped Files and Run Audit -> Power BI."
Write-Host "Use Convert Source Files when you only want to test conversion/readiness."
Write-Host "Employment Hero API credentials are optional."
