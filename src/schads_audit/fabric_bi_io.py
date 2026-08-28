from __future__ import annotations
import pandas as pd
from .fabric_io import write_df


def ensure_current_tables(spark):
    """Create stable, materialized tables used by the Direct Lake semantic model."""
    spark.sql("CREATE TABLE IF NOT EXISTS gold.current_audit_detail LIKE gold.audit_detail")
    spark.sql("CREATE TABLE IF NOT EXISTS gold.current_event_adjustments LIKE gold.audit_event_adjustments")
    spark.sql("CREATE TABLE IF NOT EXISTS gold.current_toil_findings LIKE gold.toil_findings")
    spark.sql("CREATE TABLE IF NOT EXISTS gold.current_reconciliation LIKE gold.pay_period_reconciliation")


def publish_current_snapshots(spark, result):
    """Replace BI-facing snapshots only after a successful audit has completed."""
    ensure_current_tables(spark)
    mapping = {
        "detail": "gold.current_audit_detail",
        "event_adjustments": "gold.current_event_adjustments",
        "toil_findings": "gold.current_toil_findings",
        "reconciliation": "gold.current_reconciliation",
    }
    for key, table in mapping.items():
        df = result.get(key)
        if df is None:
            continue
        if df.empty:
            # Preserve the stable table schema but remove previous snapshot rows.
            spark.sql(f"TRUNCATE TABLE {table}")
        else:
            write_df(spark, df, table, "overwrite")
