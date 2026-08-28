param(
  [string]$Config = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Config) { $Config = Join-Path $Root "fabric\config\fabric.json" }
if (-not (Test-Path $Config)) {
  throw "Missing $Config. Copy fabric/config/fabric.example.json to fabric/config/fabric.json first."
}
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
  throw "Azure CLI (az) is required."
}
az account show --output none | Out-Null

$Cfg = Get-Content $Config -Raw | ConvertFrom-Json
if ($Cfg.key_vault_url -notmatch '^https://([A-Za-z0-9-]+)\.vault\.azure\.net/?$') {
  throw "Invalid key_vault_url in $Config"
}
$VaultName = $Matches[1]
$ActualSource = [string]$Cfg.historical_defaults.actual_pay_source
if (-not $ActualSource) { $ActualSource = "PAYROLL_API" }
$ActualSource = $ActualSource.ToUpperInvariant()

Write-Host "Configuring canonical AuditHero secrets in Azure Key Vault: $VaultName"

function Set-AuditHeroSecret {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [switch]$Optional
  )
  do {
    $Secure = Read-Host "Enter $Name$(if ($Optional) {' (blank to skip)'})" -AsSecureString
    $Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
      $Value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
    }
    finally {
      [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
    }
    if ($Optional -and [string]::IsNullOrWhiteSpace($Value)) {
      Write-Host "Skipped $Name"
      return
    }
  } while ([string]::IsNullOrWhiteSpace($Value))

  az keyvault secret set --vault-name $VaultName --name $Name --value $Value --output none | Out-Null
  $Value = $null
  Write-Host "✓ $Name"
}

Set-AuditHeroSecret "EH-ORGANISATION-ID"
Set-AuditHeroSecret "EH-HR-CLIENT-ID"
Set-AuditHeroSecret "EH-HR-CLIENT-SECRET"
Set-AuditHeroSecret "EH-HR-REFRESH-TOKEN"

if ($ActualSource -eq "PAYROLL_API") {
  Write-Host "Employment Hero Payroll reconciliation is enabled in the Fabric config."
  Set-AuditHeroSecret "EH-PAYROLL-API-KEY"
  Set-AuditHeroSecret "EH-PAYROLL-BUSINESS-ID"
}
else {
  Write-Host "actual_pay_source=$ActualSource; payroll API secrets are optional."
  Set-AuditHeroSecret "EH-PAYROLL-API-KEY" -Optional
  Set-AuditHeroSecret "EH-PAYROLL-BUSINESS-ID" -Optional
}

Write-Host ""
Write-Host "Key Vault values are configured."
Write-Host "NEXT:"
Write-Host "1. Ensure the Fabric notebook execution identity has Key Vault secret-read permission."
Write-Host "2. python fabric/scripts/preflight.py --config `"$Config`" --check-secrets"
Write-Host "3. .\fabric\scripts\deploy.ps1 -Config `"$Config`""
Write-Host "Secret values were not written to Git or local config files."
