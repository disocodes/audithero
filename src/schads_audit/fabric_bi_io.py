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
    "gold.current_penalties_shiftwork": "gold.award_criteria_detail",
    "gold.current_overtime_criteria": "gold.award_criteria_detail",
    "gold.current_meal_break_criteria": "gold.award_criteria_detail",
    "gold.current_sleep_broken_allowances": "gold.award_criteria_detail",
    "gold.current_evidence_required": "gold.award_criteria_detail",
}


def _column_sql_type(field) -> str:
    """Translate Spark schema types into SQL types suitable for ALTER TABLE."""
    text = field.dataType.simpleString().upper()
    aliases = {
        "INTEGER": "INT",
        "LONG": "BIGINT",
        "BOOLEAN": "BOOLEAN",
        "STRING": "STRING",
        "DOUBLE": "DOUBLE",
        "FLOAT": "FLOAT",
        "TIMESTAMP": "TIMESTAMP",
        "DATE": "DATE",
    }
    return aliases.get(text, text)


def _sync_snapshot_schema(spark, target: str, source: str) -> None:
    """Add source columns missing from an existing Direct Lake snapshot table."""
    source_fields = {field.name: field for field in spark.table(source).schema.fields}
    target_fields = {field.name for field in spark.table(target).schema.fields}
    missing = [
        f"`{name}` {_column_sql_type(field)}"
        for name, field in source_fields.items()
        if name not in target_fields
    ]
    if missing:
        _sql(
            spark,
            f"upgrading BI snapshot schema {target}",
            f"ALTER TABLE {target} ADD COLUMNS ({', '.join(missing)})",
        )
        print(f"Updated Direct Lake snapshot schema: {target} (+{len(missing)} column(s))")


def _ensure_snapshot_table(spark, target: str, source: str) -> None:
    """Create or evolve a stable Delta snapshot table from its governed source."""
    try:
        if not spark.catalog.tableExists(target):
            (
                spark.table(source)
                .limit(0)
                .write.format("delta")
                .mode("ignore")
                .saveAsTable(target)
            )
        _sync_snapshot_schema(spark, target, source)
    except Exception as exc:
        raise RuntimeError(
            f"Fabric failed preparing BI snapshot table {target} from {source}"
        ) from exc


def ensure_current_tables(spark):
    """Create/evolve materialized tables used by the Direct Lake semantic model."""
    for target, source in SNAPSHOT_SOURCES.items():
        _ensure_snapshot_table(spark, target, source)


def _replace_snapshot(spark, table: str, frame) -> None:
    if frame is None or frame.empty:
        _sql(spark, f"truncating {table}", f"TRUNCATE TABLE {table}")
    else:
        write_df(spark, frame, table, "overwrite")


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
        _replace_snapshot(spark, table, result.get(key))

    criteria = result.get("award_criteria_detail")
    if criteria is None or criteria.empty:
        for table in (
            "gold.current_penalties_shiftwork",
            "gold.current_overtime_criteria",
            "gold.current_meal_break_criteria",
            "gold.current_sleep_broken_allowances",
            "gold.current_evidence_required",
        ):
            _replace_snapshot(spark, table, None)
        return

    _replace_snapshot(
        spark,
        "gold.current_penalties_shiftwork",
        criteria[criteria["criterion_group"].isin(["PENALTIES_AND_SHIFTWORK", "PUBLIC_HOLIDAYS", "MINIMUM_ENGAGEMENT"])].copy(),
    )
    _replace_snapshot(
        spark,
        "gold.current_overtime_criteria",
        criteria[criteria["criterion_group"] == "OVERTIME"].copy(),
    )
    _replace_snapshot(
        spark,
        "gold.current_meal_break_criteria",
        criteria[criteria["criterion_group"] == "MEAL_BREAKS"].copy(),
    )
    _replace_snapshot(
        spark,
        "gold.current_sleep_broken_allowances",
        criteria[criteria["criterion_group"].isin(["SLEEPOVER", "BROKEN_SHIFT", "MINIMUM_ENGAGEMENT", "ALLOWANCES"])].copy(),
    )
    _replace_snapshot(
        spark,
        "gold.current_evidence_required",
        criteria[criteria["criterion"] == "EVIDENCE_OR_RULE_REVIEW"].copy(),
    )
