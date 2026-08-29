# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Rule Rate History
# MAGIC
# MAGIC **Purpose:** show the effective-dated base-rate history for one canonical classification code. This is a reference/validation notebook; it does not inspect employee payroll and does not change audit results.
# COMMAND ----------
exec(open(str(Path.cwd() / "_common.py")).read())

import pandas as pd
from schads_audit.rules import RuleLibrary
# COMMAND ----------
# MAGIC %md
# MAGIC ## Choose a canonical classification
# MAGIC
# MAGIC Use a code available in the AuditHero rule library, for example `SACS-L2-P3`.
# COMMAND ----------
dbutils.widgets.text("classification_code", "SACS-L2-P3")
classification_code = dbutils.widgets.get("classification_code")
lib = RuleLibrary(ROOT / "rules/MA000100")
# COMMAND ----------
# MAGIC %md
# MAGIC ## Resolve that classification against each rate-pack operative date
# MAGIC
# MAGIC This display is useful when validating historical source mappings or explaining which base rate became available with a new pay-guide version.
# COMMAND ----------
rows = []
for pack in lib.rate_packs:
    rate, _ = lib.rate(classification_code, pack["operative_date"])
    rows.append(
        {
            "operative_date": pack["operative_date"],
            "classification_code": classification_code,
            "base_hourly_rate": rate["base_hourly_rate"] if rate else None,
            "source": pack["source"].get("title"),
        }
    )

display(pd.DataFrame(rows).sort_values("operative_date"))
