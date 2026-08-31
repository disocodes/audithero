# Databricks notebook source
# MAGIC %md
# MAGIC ## Shared notebook bootstrap
# MAGIC
# MAGIC This small helper is loaded by the other AuditHero Databricks notebooks. It finds the checked-out AuditHero repository and adds `src/` to Python's import path so every notebook uses the same `schads_audit` package. It does **not** calculate payroll or modify data.
# COMMAND ----------
from pathlib import Path
import sys

# Walk upward from the current notebook location until the repository root is found.
ROOT = next(
    (
        p
        for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents]
        if (p / "databricks.yml").exists()
    ),
    None,
)
if ROOT is None:
    raise RuntimeError("AuditHero repository root could not be found")

# Import the version of AuditHero that belongs to this deployed repository.
source_path = str(ROOT / "src")
if source_path not in sys.path:
    sys.path.insert(0, source_path)
