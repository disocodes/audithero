# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Rule Rate History
# MAGIC
# MAGIC **Purpose:** display the effective-dated base-rate history for one canonical classification code. This notebook does not inspect employee payroll or change audit results.
# COMMAND ----------
from pathlib import Path

exec(open(str(Path.cwd() / "_common.py")).read())

import pandas as pd
from schads_audit.rules import RuleLibrary
# COMMAND ----------
# MAGIC %md
# MAGIC ## Choose a canonical classification
# MAGIC
# MAGIC Enter a classification code available in the AuditHero rule library, for example `SACS-L2-P3`.
# COMMAND ----------
dbutils.widgets.text("classification_code", "SACS-L2-P3")
classification_code = dbutils.widgets.get("classification_code")
lib = RuleLibrary(ROOT / "rules/MA000100")
# COMMAND ----------
# MAGIC %md
# MAGIC ## Display the effective-dated rate history
# MAGIC
# MAGIC The result lists the base rate resolved for the selected classification at each rate-pack operative date.
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
