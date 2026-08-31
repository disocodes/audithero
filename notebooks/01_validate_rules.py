# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Validate SCHADS Rule Library
# MAGIC
# MAGIC **Purpose:** confirm that the source-controlled MA000100 rate, condition and allowance packs can be loaded before they are used in an audit.
# MAGIC
# MAGIC This notebook is a rule-library health check. It does not read employee data or calculate under/over-payment.
# COMMAND ----------
exec(open(str(Path.cwd() / "_common.py")).read())

import pandas as pd
from schads_audit.rules import RuleLibrary
# COMMAND ----------
# MAGIC %md
# MAGIC ## Load and validate the rule packs
# MAGIC
# MAGIC Validation stops on malformed/missing rule content. A successful result then displays the coverage rows so an administrator can see the operative dates currently available.
# COMMAND ----------
lib = RuleLibrary(ROOT / "rules/MA000100")
errors = lib.validate()
if errors:
    raise ValueError("\n".join(errors))

coverage = pd.DataFrame(lib.coverage_rows()).sort_values(["pack_type", "operative_date"])
display(coverage)
print("Rule library validation passed.")
