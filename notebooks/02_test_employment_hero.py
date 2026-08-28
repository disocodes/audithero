# Databricks notebook source
# MAGIC %pip install "requests>=2.32"
# COMMAND ----------
exec(open(str(Path.cwd()/'_common.py')).read());from schads_audit.config import AuditConfig;from schads_audit.employment_hero_hr import EmploymentHeroHRClient
dbutils.widgets.text('secret_scope','audithero');scope=dbutils.widgets.get('secret_scope');cfg=AuditConfig(secret_scope=scope);secret=lambda k:dbutils.secrets.get(scope=scope,key=k);c=EmploymentHeroHRClient(secret('EH_HR_CLIENT_ID'),secret('EH_HR_CLIENT_SECRET'),secret('EH_HR_REFRESH_TOKEN'),cfg.hr_base_url,cfg.hr_token_url);org=secret('EH_ORGANISATION_ID');print('Employees',len(c.employees(org)));print('Awards/classifications',len(c.awards_and_classifications(org)));print('Pay categories',len(c.pay_categories(org)));print('Work types',len(c.work_types(org)))
