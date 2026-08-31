param(
  [string]$Scope = "audithero"
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command databricks -ErrorAction SilentlyContinue)) {
  throw "Databricks CLI is required."
}

databricks secrets create-scope $Scope 2>$null

function Set-AuditHeroSecret([string]$Key) {
  $secure = Read-Host "Enter $Key" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    databricks secrets put-secret $Scope $Key --string-value $value
    if ($LASTEXITCODE -ne 0) { throw "Failed to store $Key" }
  }
  finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

Set-AuditHeroSecret "EH_ORGANISATION_ID"
Set-AuditHeroSecret "EH_HR_CLIENT_ID"
Set-AuditHeroSecret "EH_HR_CLIENT_SECRET"
Set-AuditHeroSecret "EH_HR_REFRESH_TOKEN"

$payroll = Read-Host "Configure Employment Hero Payroll API? [y/N]"
if ($payroll -match '^[Yy]$') {
  Set-AuditHeroSecret "EH_PAYROLL_API_KEY"
  Set-AuditHeroSecret "EH_PAYROLL_BUSINESS_ID"
}

Write-Host "AuditHero Databricks secrets configured in scope '$Scope'."
