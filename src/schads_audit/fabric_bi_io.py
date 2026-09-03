from __future__ import annotations
from .fabric_io import _sql, write_df


SNAPSHOT_SOURCES = {
    "gold.current_audit_detail": "gold.audit_detail",
    "gold.current_rest_break_findings": "gold.rest_break_findings",
    "gold.current_event_adjustments": "gold.audit_event_adjustments",
    "gold.current_toil_findings": "gold.toil_findings",
    "gold.current_reconciliation": "gold.pay_period_reconciliation",
    "gold.current_award_scenario_detail": "gold.award_scenario_detail",
    "gold.current_award_criteria_detail": "gold.award_criteria_detail",
    "gold.current_award_scenario_rest_findings": "gold.award_scenario_rest_findings",
}


def _ensure_snapshot_table(spark, target: str, source: str) -> None:
    """Create an empty Delta snapshot table with the source table's exact schema."""
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
    """Create stable materialized tables used by the Direct Lake semantic model."""
    for target, source in SNAPSHOT_SOURCES.items():
        _ensure_snapshot_table(spark, target, source)


def publish_current_snapshots(spark, result):
    """Replace BI-facing snapshots only after a successful audit has completed."""
    ensure_current_tables(spark)
    mapping = {
        "detail": "gold.current_audit_detail",
        "rest_break_findings": "gold.current_rest_break_findings",
        "event_adjustments": "gold.current_event_adjustments",
        "toil_findings": "gold.current_toil_findings",
        "reconciliation": "gold.current_reconciliation",
        "award_scenario_detail": "gold.current_award_scenario_detail",
        "award_criteria_detail": "gold.current_award_criteria_detail",
        "award_scenario_rest_findings": "gold.current_award_scenario_rest_findings",
    }
    for key, table in mapping.items():
        df = result.get(key)
        if df is None:
            continue
        if df.empty:
            _sql(spark, f"truncating {table}", f"TRUNCATE TABLE {table}")
        else:
            write_df(spark, df, table, "overwrite")
