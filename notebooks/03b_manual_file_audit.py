# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Audit Prepared or Canonical CSV / Excel
# MAGIC
# MAGIC **Purpose:** run a file-based AuditHero payroll audit from reviewed canonical CSV files or `audithero_input.xlsx`.
# MAGIC
# MAGIC For automatically prepared uploads, review `auto_intake_preview.csv` first. If the interpretation is correct, run this notebook/job against the prepared folder. If correction is required, use the Advanced Mapping workflow instead.
# COMMAND ----------
# MAGIC %pip install "pandas>=2.0" "openpyxl>=3.1" "holidays>=0.75"
# COMMAND ----------
from pathlib import Path
import json
from time import perf_counter

exec(open(str(Path.cwd() / "_common.py")).read())

from datetime import date, datetime, timezone
import uuid
import pandas as pd

from schads_audit.dates import iso_date, parse_datetime_series
from schads_audit.rules import RuleLibrary
from schads_audit.manual_audit import run_manual_audit
from schads_audit.databricks_io import write_df, create_views, _prepare_pandas_for_spark
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Set the input folder and audit dates
# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("input_root", "")
dbutils.widgets.text("start_date", "")
dbutils.widgets.text("end_date", "")
dbutils.widgets.text("run_type", "MANUAL_FILE")

catalog = dbutils.widgets.get("catalog")
input_root = dbutils.widgets.get("input_root").strip() or f"/Volumes/{catalog}/bronze/landing/input"
start_date = dbutils.widgets.get("start_date").strip()
end_date = dbutils.widgets.get("end_date").strip()
run_type = dbutils.widgets.get("run_type").strip() or "MANUAL_FILE"

if bool(start_date) != bool(end_date):
    raise ValueError(
        "Supply both start_date and end_date, or leave both blank to use the date range from auto_intake_manifest.json. "
        f"Received start_date={start_date!r}, end_date={end_date!r}."
    )

manifest_path = Path(input_root) / "auto_intake_manifest.json"
window_source = "JOB_PARAMETERS"
if not start_date and not end_date:
    if not manifest_path.exists():
        raise ValueError("Audit dates were not supplied and auto_intake_manifest.json was not found in the prepared input folder.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    start_date = str(manifest.get("audit_start_date") or manifest.get("start_date") or "").strip()
    end_date = str(manifest.get("audit_end_date") or manifest.get("end_date") or "").strip()
    window_source = "AUTO_INTAKE_MANIFEST"
if not start_date or not end_date:
    raise ValueError("Audit dates could not be determined. Supply both start_date/end_date or rerun the preview job with a valid date window.")

start_iso = iso_date(start_date)
end_iso = iso_date(end_date)
if pd.Timestamp(end_iso) < pd.Timestamp(start_iso):
    raise ValueError(f"end_date must be on or after start_date: {start_date} to {end_date}")

print(f"Input folder: {input_root}")
print(f"Audit window source: {window_source}")
print(f"Audit window entered/detected: {start_date} to {end_date}")
print(f"Audit window resolved: {start_iso} to {end_iso}")
print("Audit scope: full AuditHero calculation and Award scenario analysis for the requested date window")
print(f"Run type: {run_type}")
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run the file-based audit engine
# COMMAND ----------
run_id = str(uuid.uuid4())
started = datetime.now(timezone.utc)
lib = RuleLibrary(ROOT / "rules/MA000100")

classification_catalog = {}
for pack in lib.rate_packs:
    family = str(pack.get("classification_family") or "OTHER")
    for rate in pack.get("rates", []):
        code = str(rate.get("classification_code") or "").strip()
        if code:
            classification_catalog[code] = family
scenario_passes = 0
for family in classification_catalog.values():
    work_group_count = 2 if family == "HOME_CARE_DISABILITY" else 1
    scenario_passes += work_group_count * 3
print(f"Full Award scenario passes configured: {scenario_passes}")

engine_started = perf_counter()
result = run_manual_audit(
    input_root,
    ROOT / "config",
    start_iso,
    end_iso,
    lib,
    generate_award_scenarios=True,
)
engine_seconds = perf_counter() - engine_started
finished = datetime.now(timezone.utc)

print(f"Audit calculation phase completed in {engine_seconds:.1f}s")
print("Rows retained for requested audit window:")
for name in ("timesheets", "rostered_shifts", "payroll_earnings", "pay_details", "employment_history"):
    frame = result.get(name)
    print(f"  {name}: {0 if frame is None else len(frame):,}")
print("Calculated output sizes:")
for name in ("detail", "reconciliation", "award_scenario_detail", "award_criteria_detail", "award_scenario_rest_findings"):
    frame = result.get(name)
    print(f"  {name}: {0 if frame is None else len(frame):,}")
# COMMAND ----------
for frame in (
    result["detail"], result["rest_break_findings"], result["event_adjustments"],
    result["toil_findings"], result["reconciliation"], result["award_scenario_detail"],
    result["award_criteria_detail"], result["award_scenario_rest_findings"],
):
    if frame is not None and not frame.empty:
        frame["audit_run_id"] = run_id
        frame["audit_window_start"] = start_iso
        frame["audit_window_end"] = end_iso
        frame["run_type"] = run_type
        frame["run_finished_at"] = finished
# COMMAND ----------
persist_started = perf_counter()
print("Persisting filtered source evidence and calculated results with schema-safe row-level upserts...")

from pyspark.sql import functions as F

# Stable business-key candidates. The first candidate whose columns exist in both
# source and target is used. Keys deliberately exclude run metadata so rerunning
# the same evidence updates the same logical row instead of creating duplicates.
MERGE_KEY_CANDIDATES = {
    "employees": [("employee_id",)],
    "pay_details": [("employee_id", "effective_from"), ("employee_id", "classification_code", "effective_from")],
    "employment_history": [("employee_id", "start_date"), ("employee_id", "start_date", "end_date")],
    "timesheets": [("timesheet_id",)],
    "rostered_shifts": [("rostered_shift_id",), ("roster_shift_id",), ("shift_id",), ("employee_id", "rostered_start_datetime", "rostered_end_datetime")],
    "payroll_earnings": [("payroll_earning_id",), ("earning_id",), ("employee_id", "pay_period_start", "pay_period_end", "pay_category", "earning_date")],
    "public_holidays": [("state", "holiday_date", "holiday_name", "holiday_location_key")],
    "audit_detail": [("timesheet_id",)],
    "rest_break_findings": [("employee_id", "previous_shift_end", "next_shift_start", "finding_type")],
    "audit_event_adjustments": [("event_id",), ("employee_id", "event_type", "start_datetime", "end_datetime")],
    "toil_findings": [("toil_id",), ("employee_id", "overtime_datetime", "agreement_date")],
    "pay_period_reconciliation": [("employee_id", "pay_period_start", "pay_period_end")],
    "award_scenario_detail": [("scenario_id", "timesheet_id")],
    "award_criteria_detail": [("scenario_id", "timesheet_id", "criterion_group", "criterion", "clause")],
    "award_scenario_rest_findings": [("scenario_id", "employee_id", "previous_shift_end", "next_shift_start", "finding_type")],
}

VOLATILE_COLUMNS = {"audit_run_id", "ingested_at", "run_finished_at"}
TEMPORAL_COLUMNS = {
    "pay_period_start", "pay_period_end", "shift_start", "shift_end",
    "start_datetime", "end_datetime", "rostered_start_datetime", "rostered_end_datetime",
    "previous_shift_end", "next_shift_start", "overtime_datetime", "agreement_date",
    "earning_date", "holiday_date", "effective_from", "start_date", "end_date",
    "audit_window_start", "audit_window_end", "award_reference_date",
    "ingested_at", "run_finished_at", "started_at", "finished_at",
}
NUMERIC_PREFIXES = ("tinyint", "smallint", "int", "bigint", "float", "double", "decimal(")


def _table_leaf(table):
    return table.split(".")[-1].replace("`", "")


def _merge_keys(table, columns):
    available = set(columns)
    for candidate in MERGE_KEY_CANDIDATES.get(_table_leaf(table), []):
        if set(candidate).issubset(available):
            return list(candidate)
    fallback = [
        c for c in ("scenario_id", "timesheet_id", "employee_id", "pay_period_start", "pay_period_end", "shift_start")
        if c in available
    ]
    return fallback


def _q(name):
    return f"`{str(name).replace('`', '``')}`"


def _is_numeric_type(type_name):
    return str(type_name).lower().startswith(NUMERIC_PREFIXES)


def _is_timestamp_type(type_name):
    return str(type_name).lower().startswith("timestamp")


def _prepare_upsert_pandas(frame):
    """Preserve real temporal values before Spark Connect schema inference.

    Pandas object columns can contain Timestamp/datetime values plus nulls. Spark
    Connect can infer those mixed object columns as DOUBLE. That is how a logical
    pay_period_start reached MERGE as DOUBLE while the Delta target was TIMESTAMP.
    Convert temporal object/datetime columns to Python datetime objects first.
    Numeric temporal columns are accepted only when they clearly look like Unix
    seconds/milliseconds/microseconds/nanoseconds; small ambiguous numerics fail
    closed rather than being guessed as dates.
    """
    out = frame.copy()
    for name in out.columns:
        series = out[name]
        parsed = None

        if pd.api.types.is_datetime64_any_dtype(series.dtype):
            parsed = pd.to_datetime(series, errors="coerce")
        elif pd.api.types.is_object_dtype(series.dtype):
            populated = series[series.notna()]
            if not populated.empty and populated.map(lambda v: isinstance(v, (pd.Timestamp, datetime, date))).any():
                parsed = parse_datetime_series(series)
        elif name in TEMPORAL_COLUMNS and pd.api.types.is_numeric_dtype(series.dtype):
            numeric = pd.to_numeric(series, errors="coerce")
            magnitude_values = numeric.dropna().abs()
            if not magnitude_values.empty:
                magnitude = float(magnitude_values.median())
                if magnitude >= 1e17:
                    parsed = pd.to_datetime(numeric, unit="ns", errors="coerce")
                elif magnitude >= 1e14:
                    parsed = pd.to_datetime(numeric, unit="us", errors="coerce")
                elif magnitude >= 1e11:
                    parsed = pd.to_datetime(numeric, unit="ms", errors="coerce")
                elif magnitude >= 1e8:
                    parsed = pd.to_datetime(numeric, unit="s", errors="coerce")
                else:
                    raise ValueError(
                        f"Refusing to guess numeric temporal values in {name!r}; "
                        f"observed magnitude {magnitude:g}. Supply an actual date/datetime value."
                    )

        if parsed is not None:
            meaningful = series.notna()
            invalid = meaningful & parsed.isna()
            if bool(invalid.any()):
                sample = series.loc[invalid].astype(str).head(3).tolist()
                raise ValueError(f"Invalid temporal value(s) in {name}: {sample}")
            out[name] = parsed.map(lambda v: None if pd.isna(v) else v.to_pydatetime())

    return _prepare_pandas_for_spark(out)


def _numeric_epoch_to_timestamp(column_name):
    """Convert obvious epoch numeric representations to a Spark timestamp."""
    value = F.col(column_name).cast("double")
    magnitude = F.abs(value)
    seconds = (
        F.when(magnitude >= F.lit(1e17), value / F.lit(1e9))
        .when(magnitude >= F.lit(1e14), value / F.lit(1e6))
        .when(magnitude >= F.lit(1e11), value / F.lit(1e3))
        .when(magnitude >= F.lit(1e8), value)
        .otherwise(F.lit(None).cast("double"))
    )
    return F.to_timestamp(F.from_unixtime(seconds.cast("long")))


def _validated_replace(incoming, table, name, converted, source_type, target_type):
    bad = incoming.where(F.col(name).isNotNull() & converted.isNull()).limit(1).count()
    if bad:
        return incoming, False, f"{name}({source_type}->{target_type})"
    return incoming.withColumn(name, converted), True, f"{name}({source_type}->{target_type})"


def _align_incoming_to_target(incoming, existing, table):
    """Align source columns to existing Delta types before building MERGE SQL.

    Temporal and safe numeric mismatches are fixed on the source side. Genuine
    semantic conflicts (for example a legacy DOUBLE column now carrying real text)
    are returned for one-time target schema repair instead of being silently cast.
    """
    existing_types = {f.name: f.dataType.simpleString() for f in existing.schema.fields}
    incoming_types = {f.name: f.dataType.simpleString() for f in incoming.schema.fields}
    aligned = incoming
    changes = []
    unresolved = []

    for name, source_type in incoming_types.items():
        if name not in existing_types:
            continue
        target_type = existing_types[name]
        if source_type == target_type:
            continue

        converted = None
        if target_type == "string":
            converted = F.col(name).cast("string")
        elif _is_timestamp_type(target_type):
            if _is_numeric_type(source_type):
                converted = _numeric_epoch_to_timestamp(name).cast(target_type)
            elif source_type == "date":
                converted = F.col(name).cast(target_type)
            else:
                converted = F.coalesce(
                    F.expr(f"try_cast({_q(name)} AS TIMESTAMP)"),
                    F.expr(f"try_to_timestamp({_q(name)}, 'dd-MM-yyyy')"),
                    F.expr(f"try_to_timestamp({_q(name)}, 'dd/MM/yyyy')"),
                ).cast(target_type)
        elif target_type == "date":
            if _is_numeric_type(source_type):
                converted = F.to_date(_numeric_epoch_to_timestamp(name))
            elif _is_timestamp_type(source_type):
                converted = F.col(name).cast("date")
            else:
                converted = F.coalesce(
                    F.expr(f"try_cast({_q(name)} AS DATE)"),
                    F.to_date(F.col(name), "dd-MM-yyyy"),
                    F.to_date(F.col(name), "dd/MM/yyyy"),
                )
        elif _is_numeric_type(target_type) and _is_numeric_type(source_type):
            converted = F.col(name).cast(target_type)
        elif _is_numeric_type(target_type) and source_type == "string":
            # Numeric-looking strings are safe to align. Real text is not; it means
            # the old table inferred the wrong type and must be widened to STRING.
            candidate = F.expr(f"try_cast({_q(name)} AS {target_type})")
            aligned_candidate, ok, detail = _validated_replace(aligned, table, name, candidate, source_type, target_type)
            if ok:
                aligned = aligned_candidate
                changes.append(detail)
            else:
                unresolved.append(name)
            continue
        elif target_type == "boolean":
            converted = F.expr(f"try_cast({_q(name)} AS BOOLEAN)")
        else:
            candidate = F.expr(f"try_cast({_q(name)} AS {target_type})")
            aligned_candidate, ok, detail = _validated_replace(aligned, table, name, candidate, source_type, target_type)
            if ok:
                aligned = aligned_candidate
                changes.append(detail)
            else:
                unresolved.append(name)
            continue

        aligned_candidate, ok, detail = _validated_replace(aligned, table, name, converted, source_type, target_type)
        if ok:
            aligned = aligned_candidate
            changes.append(detail)
        else:
            unresolved.append(name)

    return aligned, changes, unresolved


def _repair_legacy_target_types(table, existing, incoming, columns):
    """Rewrite only when an old target schema is semantically wrong.

    Existing rows are preserved. A temporary Delta table is materialised with the
    corrected types, then copied back over the original table with overwriteSchema.
    This avoids the earlier failure-prone union of incompatible source/target types.
    """
    incoming_types = {f.name: f.dataType.simpleString() for f in incoming.schema.fields}
    migrated = existing
    repairs = []

    for name in columns:
        target_type = incoming_types[name]
        if target_type != "string":
            raise ValueError(
                f"Unsupported legacy schema conflict for {table}.{name}: target={existing.schema[name].dataType.simpleString()} "
                f"incoming={target_type}. AuditHero will not guess a destructive type conversion."
            )
        migrated = migrated.withColumn(name, F.col(name).cast("string"))
        repairs.append(f"{name}->{target_type}")

    parts = table.replace("`", "").split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected catalog.schema.table name, got {table!r}")
    temp_table = f"{parts[0]}.{parts[1]}._audithero_schema_repair_{parts[2]}_{uuid.uuid4().hex[:8]}"

    try:
        migrated.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(temp_table)
        spark.table(temp_table).write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    finally:
        if spark.catalog.tableExists(temp_table):
            spark.sql(f"DROP TABLE {temp_table}")

    print(f"  {table}: preserved existing rows while repairing legacy type(s): {', '.join(repairs)}")


def _upsert_frame(frame, table):
    if frame is None or frame.empty:
        return

    prepared = _prepare_upsert_pandas(frame)
    incoming = spark.createDataFrame(prepared)

    if not spark.catalog.tableExists(table):
        incoming.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
        print(f"  {table}: created {incoming.count():,} row(s)")
        return

    existing = spark.table(table)
    incoming, aligned_changes, unresolved = _align_incoming_to_target(incoming, existing, table)
    if aligned_changes:
        print(f"  {table}: aligned incoming schema: {', '.join(aligned_changes)}")

    if unresolved:
        _repair_legacy_target_types(table, existing, incoming, unresolved)
        existing = spark.table(table)
        incoming, aligned_changes_after_repair, unresolved_after_repair = _align_incoming_to_target(incoming, existing, table)
        if unresolved_after_repair:
            details = ", ".join(unresolved_after_repair)
            raise ValueError(f"Schema remains incompatible after repair for {table}: {details}")
        if aligned_changes_after_repair:
            print(f"  {table}: post-repair alignment: {', '.join(aligned_changes_after_repair)}")

    existing_columns = set(existing.columns)
    common_columns = [c for c in incoming.columns if c in existing_columns]
    missing_columns = [c for c in incoming.columns if c not in existing_columns]
    keys = _merge_keys(table, common_columns)

    if not keys:
        print(f"  {table}: no stable business key found; appending exact-schema rows")
        incoming.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)
        return

    # Exact duplicate rows in the incoming batch are harmless. Distinct rows with
    # the same business key are ambiguous and must not be merged arbitrarily.
    incoming = incoming.dropDuplicates()
    duplicate_key = incoming.groupBy(*keys).count().where(F.col("count") > 1).limit(1).count()
    if duplicate_key:
        raise ValueError(f"Ambiguous duplicate business key in current data for {table}: {keys}")

    temp_view = f"_audithero_upsert_{uuid.uuid4().hex}"
    incoming.createOrReplaceTempView(temp_view)

    key_match = " AND ".join([f"t.{_q(c)} <=> s.{_q(c)}" for c in keys])
    common_content_columns = [c for c in common_columns if c not in VOLATILE_COLUMNS]
    if missing_columns:
        # Force matched rows through UPDATE SET * so schema evolution adds and
        # populates new source columns instead of leaving them absent.
        content_equal = "FALSE"
    else:
        content_equal = " AND ".join([f"t.{_q(c)} <=> s.{_q(c)}" for c in common_content_columns]) or "TRUE"
    metadata_columns = [c for c in common_columns if c in VOLATILE_COLUMNS]
    metadata_set = ", ".join([f"t.{_q(c)} = s.{_q(c)}" for c in metadata_columns])

    merge_sql = [
        f"MERGE WITH SCHEMA EVOLUTION INTO {table} t",
        f"USING {temp_view} s",
        f"ON {key_match}",
        f"WHEN MATCHED AND NOT ({content_equal}) THEN UPDATE SET *",
    ]
    if metadata_set:
        merge_sql.append(f"WHEN MATCHED THEN UPDATE SET {metadata_set}")
    merge_sql.append("WHEN NOT MATCHED THEN INSERT *")

    try:
        spark.sql("\n".join(merge_sql))
    finally:
        spark.catalog.dropTempView(temp_view)

    extra = f"; schema-evolved columns [{', '.join(missing_columns)}]" if missing_columns else ""
    print(f"  {table}: upserted by key [{', '.join(keys)}]{extra}")


silver_frames = (
    ("employees", result["employees"]),
    ("pay_details", result["pay_details"]),
    ("employment_history", result["employment_history"]),
    ("timesheets", result["timesheets"]),
    ("rostered_shifts", result["rostered_shifts"]),
    ("payroll_earnings", result["payroll_earnings"]),
    ("public_holidays", result["public_holidays"]),
)
for name, frame in silver_frames:
    if frame is not None and not frame.empty:
        persisted = frame.copy()
        persisted["audit_run_id"] = run_id
        persisted["audit_window_start"] = start_iso
        persisted["audit_window_end"] = end_iso
        persisted["run_type"] = run_type
        persisted["ingested_at"] = finished
        _upsert_frame(persisted, f"{catalog}.silver.{name}")

for table_name, frame in (
    ("audit_detail", result["detail"]),
    ("rest_break_findings", result["rest_break_findings"]),
    ("audit_event_adjustments", result["event_adjustments"]),
    ("toil_findings", result["toil_findings"]),
    ("pay_period_reconciliation", result["reconciliation"]),
    ("award_scenario_detail", result["award_scenario_detail"]),
    ("award_criteria_detail", result["award_criteria_detail"]),
    ("award_scenario_rest_findings", result["award_scenario_rest_findings"]),
):
    _upsert_frame(frame, f"{catalog}.gold.{table_name}")

persist_seconds = perf_counter() - persist_started
print(f"Data persistence phase completed in {persist_seconds:.1f}s")
# COMMAND ----------
reconciliation = result["reconciliation"]
rest_findings = result["rest_break_findings"]
scenario_detail = result["award_scenario_detail"]
actual_source = "FILES" if result.get("actual_pay_usable", False) else "NONE"
run = pd.DataFrame([{
    "audit_run_id": run_id, "run_type": run_type, "audit_window_start": start_iso,
    "audit_window_end": end_iso, "started_at": started, "finished_at": finished,
    "status": "SUCCESS", "actual_pay_source": actual_source,
    "employees": len(result["employees"]), "timesheets": len(result["timesheets"]),
    "underpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "UNDERPAID").sum()),
    "overpaid_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "OVERPAID").sum()),
    "review_periods": int((reconciliation.get("status", pd.Series(dtype=str)) == "REQUIRES_REVIEW").sum()),
    "message": (
        f"input={input_root}; window_source={window_source}; rest_findings={len(rest_findings)}; "
        f"award_scenarios={len(scenario_detail)}; scenario_passes={scenario_passes}; "
        f"engine_seconds={engine_seconds:.1f}; persist_seconds={persist_seconds:.1f}; persistence_mode=SCHEMA_SAFE_ROW_LEVEL_UPSERT"
    ),
}])
write_df(spark, run, f"{catalog}.ops.audit_runs", "append")
create_views(spark, catalog)
# COMMAND ----------
total_seconds = (datetime.now(timezone.utc) - started).total_seconds()
print(f"Uploaded-file audit complete: {run_id}")
print(f"Performance summary: calculation={engine_seconds:.1f}s; persistence={persist_seconds:.1f}s; total={total_seconds:.1f}s")
if not reconciliation.empty:
    print(reconciliation["status"].value_counts(dropna=False).to_string())
    display(reconciliation.sort_values(["status", "employee_name"]).head(200))
if rest_findings is not None and not rest_findings.empty:
    print("\nRest-between-work findings:")
    print(rest_findings["status"].value_counts(dropna=False).to_string())
if scenario_detail is not None and not scenario_detail.empty:
    print(f"\nAward scenario rows available for interactive level/pay-point analysis: {len(scenario_detail):,}")
print("Recommended next step: review the AuditHero dashboard, exceptions and supporting evidence.")
