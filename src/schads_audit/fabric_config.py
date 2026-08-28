from __future__ import annotations
from dataclasses import dataclass


@dataclass
class FabricAuditConfig:
    key_vault_url: str
    timezone: str = "Australia/Perth"
    variance_tolerance: float = 0.05
    actual_pay_source: str = "PAYROLL_API"
    hr_base_url: str = "https://api.employmenthero.com/api/v1"
    hr_token_url: str = "https://oauth.employmenthero.com/oauth2/token"
    payroll_base_url: str = "https://api.yourpayroll.com.au/api/v2"
    config_root: str = "/lakehouse/default/Files/config"

    organisation_secret: str = "EH-ORGANISATION-ID"
    hr_client_id_secret: str = "EH-HR-CLIENT-ID"
    hr_client_secret_secret: str = "EH-HR-CLIENT-SECRET"
    hr_refresh_token_secret: str = "EH-HR-REFRESH-TOKEN"
    payroll_api_key_secret: str = "EH-PAYROLL-API-KEY"
    payroll_business_id_secret: str = "EH-PAYROLL-BUSINESS-ID"
