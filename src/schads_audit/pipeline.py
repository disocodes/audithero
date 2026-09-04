"""Backward-compatible Databricks pipeline entry point.

The production Databricks implementation is ``databricks_pipeline_v2``. This
module remains only for external callers that imported ``run_databricks_audit``
from older AuditHero releases. Keeping one execution implementation prevents
legacy logic from diverging from the production compliance stages.
"""

from .databricks_pipeline_v2 import run_databricks_audit_v2


def run_databricks_audit(
    spark,
    dbutils,
    config,
    lib,
    start_date,
    end_date,
    mapping_dir,
    run_type="HISTORICAL",
    actual_pay_source=None,
):
    """Delegate the legacy API to the current production Databricks pipeline."""
    return run_databricks_audit_v2(
        spark,
        dbutils,
        config,
        lib,
        start_date,
        end_date,
        mapping_dir,
        run_type=run_type,
        actual_pay_source=actual_pay_source,
    )


__all__ = ["run_databricks_audit", "run_databricks_audit_v2"]
