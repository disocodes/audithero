param(
  [string]$Config = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Config) { $Config = Join-Path $Root "fabric\config\fabric.json" }
if (-not (Test-Path $Config)) {
  throw "Missing $Config. Copy fabric/config/fabric.example.json to fabric/config/fabric.json and configure it."
}
python -m pip install --quiet "requests>=2.32" "build>=1.2"
python (Join-Path $Root "fabric\scripts\deploy_fabric.py") --config $Config
