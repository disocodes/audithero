param(
  [string]$Scope = "audithero"
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command databricks -ErrorAction SilentlyContinue)) {
  throw "Databricks CLI is required."
}
databricks current-user me --output json | Out-Null

try { databricks secrets create-scope $Scope | Out-Null } catch { }

function Set-DatabricksSecret {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [switch]$Optional
  )
  do {
    $Secure = Read-Host "Enter $Name$(if ($Optional) {' (blank to skip)'})" -AsSecureString
    $Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { $Value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr) }

    if ($Optional -and [string]::IsNullOrWhiteSpace($Value)) {
      Write-Host "Skipped $Name"
      return
    }
  } while ([string]::IsNullOrWhiteSpace($Value))

  databricks secrets put-secret $Scope $Name --string-value $Value | Out-Null
  $Value = $null
  Write-Host "✓ $Name"
}

Set-DatabricksSecret "EH_ORGANISATION_ID"
Set-DatabricksSecret "EH_HR_CLIENT_ID"
Set-DatabricksSecret "EH_HR_CLIENT_SECRET"
Set-DatabricksSecret "EH_HR_REFRESH_TOKEN"

$UsePayroll = Read-Host "Configure Employment Hero Payroll API for actual-pay reconciliation? [Y/n]"
if ([string]::IsNullOrWhiteSpace($UsePayroll)) { $UsePayroll = "Y" }
if ($UsePayroll -match '^[Yy]') {
  Set-DatabricksSecret "EH_PAYROLL_API_KEY"
  Set-DatabricksSecret "EH_PAYROLL_BUSINESS_ID"
}
else {
  Set-DatabricksSecret "EH_PAYROLL_API_KEY" -Optional
  Set-DatabricksSecret "EH_PAYROLL_BUSINESS_ID" -Optional
}

Write-Host ""
Write-Host "Databricks secret scope '$Scope' is configured."
Write-Host "NEXT: complete config mappings/registers, then run:"
Write-Host "  databricks bundle run connection_test"
Write-Host "  databricks bundle run audit_readiness"
