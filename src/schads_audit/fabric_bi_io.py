from __future__ import annotations
import pandas as pd
from .fabric_io import _sql, write_df


def ensure_current_tables(spark):
    """Create stable, materialized tables used by the Direct Lake semantic model."""
    statements = [
        (
            "creating gold.current_audit_detail",
            "CREATE TABLE IF NOT EXISTS gold.current_audit_detail LIKE gold.audit_detail",
        ),
        (
            "creating gold.current_event_adjustments",
            "CREATE TABLE IF NOT EXISTS gold.current_event_adjustments LIKE gold.audit_event_adjustments",
        ),
        (
            "creating gold.current_toil_findings",
            "CREATE TABLE IF NOT EXISTS gold.current_toil_findings LIKE gold.toil_findings",
        ),
        (
            "creating gold.current_reconciliation",
            "CREATE TABLE IF NOT EXISTS gold.current_reconciliation LIKE gold.pay_period_reconciliation",
        ),
    ]
    for label, statement in statements:
        _sql(spark, label, statement)


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
            _sql(spark, f"truncating {table}", f"TRUNCATE TABLE {table}")
        else:
            write_df(spark, df, table, "overwrite")
