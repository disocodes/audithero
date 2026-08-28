# Parameters supplied by Fabric pipeline/deployer:
# key_vault_url
from schads_audit.fabric_config import FabricAuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient

cfg = FabricAuditConfig(key_vault_url=key_vault_url)
secret = lambda name: notebookutils.credentials.getSecret(cfg.key_vault_url, name)
client = EmploymentHeroHRClient(
    secret(cfg.hr_client_id_secret),
    secret(cfg.hr_client_secret_secret),
    secret(cfg.hr_refresh_token_secret),
    cfg.hr_base_url,
    cfg.hr_token_url,
)
org = secret(cfg.organisation_secret)
orgs = client.organisations()
employees = client.employees(org)
awards = client.awards_and_classifications(org)
pay_categories = client.pay_categories(org)
work_types = client.work_types(org)
work_locations = client.work_locations(org)

print(f"Employment Hero HR API authenticated")
print(f"Organisations visible: {len(orgs)}")
print(f"Employees: {len(employees)}")
print(f"Award/classification metadata: {len(awards)}")
print(f"Pay categories: {len(pay_categories)}")
print(f"Work types: {len(work_types)}")
print(f"Work locations: {len(work_locations)}")
notebookutils.notebook.exit("success")
