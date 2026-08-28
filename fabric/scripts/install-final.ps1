param([string]$Config = "")
$ErrorActionPreference="Stop"
$Root=(Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Config) { $Config=Join-Path $Root "fabric\config\fabric.json" }
if (-not (Test-Path $Config)) { throw "Create $Config from fabric/config/fabric.complete.example.json" }
python -m pip install --quiet "requests>=2.32" "build>=1.2"
python (Join-Path $Root "fabric\scripts\deploy_fabric_final.py") --config $Config
