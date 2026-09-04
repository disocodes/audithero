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
python (Join-Path $Root "fabric\scripts\deploy_admin_notebooks.py") --config $Config
Write-Host ""
Write-Host "AuditHero Fabric deployment complete."
Write-Host "Primary workflow: upload ordinary CSV/XLSX files to Files/import/raw -> run AuditHero - Auto Audit Uploaded Files -> open the AuditHero Power BI report."
Write-Host "Use the report slicers to review employees, SCHADS stream, level, pay point, employment type and Award criteria."
Write-Host "Mapping/conversion jobs remain available only for unusual source layouts or controlled advanced imports."
Write-Host "Administration notebooks: AuditHero - Install or Upgrade; AuditHero - Uninstall."
Write-Host "Employment Hero API credentials are optional."
