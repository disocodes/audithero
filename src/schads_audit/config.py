from dataclasses import dataclass
import os

@dataclass
class AuditConfig:
    catalog: str = "schads_payroll"
    secret_scope: str = "audithero"
    timezone: str = "Australia/Perth"
    variance_tolerance: float = 0.05
    actual_pay_source: str = "PAYROLL_API"
    hr_base_url: str = "https://api.employmenthero.com/api/v1"
    hr_token_url: str = "https://oauth.employmenthero.com/oauth2/token"
    payroll_base_url: str = "https://api.yourpayroll.com.au/api/v2"

def from_env():
    return AuditConfig(
        catalog=os.getenv("AUDITHERO_CATALOG","schads_payroll"),
        secret_scope=os.getenv("AUDITHERO_SECRET_SCOPE","audithero"),
        timezone=os.getenv("AUDITHERO_TIMEZONE","Australia/Perth"),
        actual_pay_source=os.getenv("AUDITHERO_ACTUAL_PAY_SOURCE","PAYROLL_API").upper(),
    )
