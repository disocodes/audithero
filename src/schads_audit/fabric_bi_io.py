from __future__ import annotations
import pandas as pd
from .fabric_io import _sql, write_df


SNAPSHOT_SOURCES = {
    "gold.current_audit_detail": "gold.audit_detail",
    "gold.current_event_adjustments": "gold.audit_event_adjustments",
    "gold.current_toil_findings": "gold.toil_findings",
    "gold.current_reconciliation": "gold.pay_period_reconciliation",
}


def _ensure_snapshot_table(spark, target: str, source: str) -> None:
    """Create an empty Delta snapshot table with the source table's exact schema.

    Fabric Runtime 2.0 schema-enabled Lakehouses can mis-resolve
    ``CREATE TABLE target LIKE source`` through ``spark_catalog``.  Spark's
    DataFrame ``saveAsTable('schema.table')`` path is supported by Fabric and
    preserves the source schema without copying rows.
    """
    try:
        if spark.catalog.tableExists(target):
            return
        (
            spark.table(source)
            .limit(0)
            .write.format("delta")
            .mode("ignore")
            .saveAsTable(target)
        )
    except Exception as exc:
        raise RuntimeError(
            f"Fabric failed creating BI snapshot table {target} from {source}"
        ) from exc


def ensure_current_tables(spark):
    """Create stable, materialized tables used by the Direct Lake semantic model."""
    for target, source in SNAPSHOT_SOURCES.items():
        _ensure_snapshot_table(spark, target, source)


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
