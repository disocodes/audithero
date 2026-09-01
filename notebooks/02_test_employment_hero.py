# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Employment Hero Connection Test (Optional API)
# MAGIC
# MAGIC **Purpose:** verify that the configured Employment Hero HR API credentials can authenticate and read the metadata required by AuditHero API workflows.
# MAGIC
# MAGIC **Data access:** this notebook performs read-only API checks. It does not calculate payroll and is not required for uploaded-file audits.
# COMMAND ----------
# MAGIC %pip install "requests>=2.32"
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

from schads_audit.config import AuditConfig
from schads_audit.employment_hero_hr import EmploymentHeroHRClient
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Read the Databricks secret scope
# MAGIC
# MAGIC Secret values are not printed. The configured scope contains the Employment Hero client ID, client secret, refresh token, and organisation ID.
# COMMAND ----------
dbutils.widgets.text("secret_scope", "audithero")
scope = dbutils.widgets.get("secret_scope")
cfg = AuditConfig(secret_scope=scope)


def secret(key):
    return dbutils.secrets.get(scope=scope, key=key)

client = EmploymentHeroHRClient(
    secret("EH_HR_CLIENT_ID"),
    secret("EH_HR_CLIENT_SECRET"),
    secret("EH_HR_REFRESH_TOKEN"),
    cfg.hr_base_url,
    cfg.hr_token_url,
)
organisation_id = secret("EH_ORGANISATION_ID")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Perform read-only API checks
# MAGIC
# MAGIC The calls below verify access to the organisation and metadata endpoints required by the AuditHero API workflows. No Employment Hero records are changed.
# COMMAND ----------
print("Employment Hero connection succeeded")
print("Employees:", len(client.employees(organisation_id)))
print("Awards/classifications:", len(client.awards_and_classifications(organisation_id)))
print("Pay categories:", len(client.pay_categories(organisation_id)))
print("Work types:", len(client.work_types(organisation_id)))
print("Recommended next step: run 'AuditHero - API Audit Readiness (Optional API)' before the first API-sourced payroll audit.")
