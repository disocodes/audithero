# AuditHero — Employment Hero Connection Test (Optional API)
#
# PURPOSE
# -------
# Verify that the configured Employment Hero HR API credentials stored in Azure
# Key Vault can authenticate and read the tenant metadata required by AuditHero
# API workflows.
#
# DATA ACCESS
# ----------
# This notebook performs read-only API checks. It does not change Employment Hero
# data and does not calculate payroll. Uploaded-file audits do not require it.
#
# PARAMETER
# ---------
# key_vault_url — Azure Key Vault URL containing the AuditHero Employment Hero
# secret names.

from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient

print("STEP 1 — Resolve API credentials from Azure Key Vault")
cfg = FabricAuditConfig(key_vault_url=key_vault_url)


def secret(name):
    # notebookutils keeps secret values out of normal notebook output.
    return notebookutils.credentials.getSecret(cfg.key_vault_url, name)

client = EmploymentHeroHRClient(
    secret(cfg.hr_client_id_secret),
    secret(cfg.hr_client_secret_secret),
    secret(cfg.hr_refresh_token_secret),
    cfg.hr_base_url,
    cfg.hr_token_url,
)
organisation_id = secret(cfg.organisation_secret)

print("STEP 2 — Perform read-only metadata checks")
organisations = client.organisations()
employees = client.employees(organisation_id)
awards = client.awards_and_classifications(organisation_id)
pay_categories = client.pay_categories(organisation_id)
work_types = client.work_types(organisation_id)
work_locations = client.work_locations(organisation_id)

print("Employment Hero HR API authenticated")
print(f"Organisations visible: {len(organisations)}")
print(f"Employees: {len(employees)}")
print(f"Award/classification metadata: {len(awards)}")
print(f"Pay categories: {len(pay_categories)}")
print(f"Work types: {len(work_types)}")
print(f"Work locations: {len(work_locations)}")
print("Recommended next step: run 'AuditHero - API Audit Readiness' before the first API-sourced payroll audit.")
notebookutils.notebook.exit("success")
