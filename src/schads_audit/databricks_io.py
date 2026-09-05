import json
import pandas as pd


def create_catalog_objects(spark, catalog):
    spark.sql(f'CREATE CATALOG IF NOT EXISTS `{catalog}`')
    for schema in ('bronze','silver','ref','gold','ops','semantic'):
        spark.sql(f'CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`')
    spark.sql(f'CREATE VOLUME IF NOT EXISTS `{catalog}`.`bronze`.`landing`')


def _migrate_string_columns_for_append(spark, incoming, table):
    """Upgrade legacy Delta columns to STRING when incoming AuditHero IDs are strings.

    Older tables may have inferred numeric identifier columns from early source data.
    Auto-intake now emits stable string identifiers such as ``AUTO-TS-...``. Delta
    mergeSchema does not change BIGINT to STRING, so append would otherwise fail.
    This migration preserves existing rows, casts only incompatible legacy columns,
    and rewrites the table once with the widened schema.
    """
    if not spark.catalog.tableExists(table):
        return incoming, False

    existing = spark.table(table)
    existing_types = {field.name: field.dataType.simpleString() for field in existing.schema.fields}
    incoming_types = {field.name: field.dataType.simpleString() for field in incoming.schema.fields}
    to_string = [
        name for name, dtype in incoming_types.items()
        if dtype == 'string' and name in existing_types and existing_types[name] != 'string'
    ]
    if not to_string:
        return incoming, False

    from pyspark.sql import functions as F
    migrated = existing
    for name in to_string:
        migrated = migrated.withColumn(name, F.col(name).cast('string'))

    combined = migrated.unionByName(incoming, allowMissingColumns=True)
    combined.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').saveAsTable(table)
    print(f"Migrated legacy Delta column(s) to STRING for {table}: {', '.join(to_string)}")
    return incoming, True


def write_df(spark, df, table, mode='append'):
    if df is None or df.empty:
        return
    incoming = spark.createDataFrame(df.where(pd.notna(df), None))

    if mode == 'append':
        incoming, migrated = _migrate_string_columns_for_append(spark, incoming, table)
        if migrated:
            return

    writer = incoming.write.format('delta').mode(mode).option('mergeSchema','true')
    if mode == 'overwrite':
        writer = writer.option('overwriteSchema','true')
    writer.saveAsTable(table)


def overwrite_rule_tables(spark, lib, catalog):
    rates=[]
    for pack in lib.rate_packs:
        for row in pack['rates']:
            x=dict(row)
            x.update({'award_code':pack['award_code'],'rate_pack_id':pack['rate_pack_id'],'classification_family':pack.get('classification_family'),'operative_date':pack['operative_date'],'application_basis':pack['application_basis'],'source_json':json.dumps(pack.get('source',{}))})
            rates.append(x)
    conditions=[{'award_code':p['award_code'],'condition_pack_id':p['condition_pack_id'],'operative_date':p['operative_date'],'condition_json':json.dumps(p)} for p in lib.condition_packs]
    allowances=[]
    for pack in lib.allowance_packs:
        for row in pack['allowances']:
            x=dict(row)
            x.update({'award_code':pack['award_code'],'allowance_pack_id':pack['allowance_pack_id'],'operative_date':pack['operative_date'],'source_json':json.dumps(pack.get('source',{}))})
            allowances.append(x)
    write_df(spark,pd.DataFrame(rates),f'{catalog}.ref.rates','overwrite')
    write_df(spark,pd.DataFrame(conditions),f'{catalog}.ref.conditions','overwrite')
    write_df(spark,pd.DataFrame(allowances),f'{catalog}.ref.allowances','overwrite')
    write_df(spark,pd.DataFrame(lib.coverage_rows()),f'{catalog}.ref.rule_coverage','overwrite')


def create_views(spark, catalog):
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_latest_audit_runs` AS SELECT * FROM `{catalog}`.`ops`.`audit_runs` WHERE status='SUCCESS' QUALIFY ROW_NUMBER() OVER (PARTITION BY audit_window_start,audit_window_end ORDER BY finished_at DESC)=1''')
    latest = {
        'v_audit_detail_latest': 'audit_detail',
        'v_event_adjustments_latest': 'audit_event_adjustments',
        'v_toil_findings_latest': 'toil_findings',
        'v_rest_break_findings_latest': 'rest_break_findings',
        'v_reconciliation_latest': 'pay_period_reconciliation',
        'v_award_scenario_detail_latest': 'award_scenario_detail',
        'v_award_criteria_detail_latest': 'award_criteria_detail',
        'v_award_scenario_rest_findings_latest': 'award_scenario_rest_findings',
    }
    for view, table in latest.items():
        spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`{view}` AS SELECT d.* FROM `{catalog}`.`gold`.`{table}` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_rule_coverage` AS SELECT * FROM `{catalog}`.`ref`.`rule_coverage`''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_audit_runs` AS SELECT * FROM `{catalog}`.`ops`.`audit_runs`''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_readiness_findings` AS SELECT * FROM `{catalog}`.`ops`.`readiness_findings`''')


def create_metric_views(spark, catalog):
    """Create governed metric views consumed by AI/BI and Genie."""
    payroll_yaml = f'''version: 1.1
comment: "AuditHero governed payroll compliance metrics from the latest successful audit runs"
source: {catalog}.gold.v_reconciliation_latest
fields:
  - name: employee_id
    expr: source.employee_id
  - name: employee_name
    expr: source.employee_name
  - name: pay_period_start
    expr: source.pay_period_start
  - name: pay_period_end
    expr: source.pay_period_end
  - name: status
    expr: source.status
  - name: run_type
    expr: source.run_type
  - name: audit_run_id
    expr: source.audit_run_id
measures:
  - name: employee_count
    expr: COUNT(DISTINCT source.employee_id)
  - name: pay_period_count
    expr: COUNT(1)
  - name: expected_pay
    expr: SUM(COALESCE(source.expected_amount, 0))
  - name: actual_pay
    expr: SUM(COALESCE(source.actual_auditable_amount, 0))
  - name: potential_underpayment
    expr: SUM(CASE WHEN source.status = 'UNDERPAID' THEN GREATEST(COALESCE(source.expected_amount,0) - COALESCE(source.actual_auditable_amount,0), 0) ELSE 0 END)
  - name: potential_overpayment
    expr: SUM(CASE WHEN source.status = 'OVERPAID' THEN GREATEST(COALESCE(source.actual_auditable_amount,0) - COALESCE(source.expected_amount,0), 0) ELSE 0 END)
  - name: underpaid_periods
    expr: SUM(CASE WHEN source.status = 'UNDERPAID' THEN 1 ELSE 0 END)
  - name: overpaid_periods
    expr: SUM(CASE WHEN source.status = 'OVERPAID' THEN 1 ELSE 0 END)
  - name: review_periods
    expr: SUM(CASE WHEN source.status = 'REQUIRES_REVIEW' THEN 1 ELSE 0 END)
  - name: compliant_periods
    expr: SUM(CASE WHEN source.status = 'COMPLIANT' THEN 1 ELSE 0 END)
'''
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`semantic`.`payroll_compliance` WITH METRICS LANGUAGE YAML AS $$\n{payroll_yaml}\n$$''')

    detail_yaml = f'''version: 1.1
comment: "AuditHero shift-level entitlement metrics from the latest successful audit runs"
source: {catalog}.gold.v_audit_detail_latest
fields:
  - name: employee_id
    expr: source.employee_id
  - name: employee_name
    expr: source.employee_name
  - name: employment_type
    expr: source.employment_type
  - name: classification_code
    expr: source.classification_code
  - name: work_group
    expr: source.work_group
  - name: state
    expr: source.state
  - name: pay_period_start
    expr: source.pay_period_start
  - name: pay_period_end
    expr: source.pay_period_end
  - name: shift_start
    expr: source.shift_start
  - name: entitlement_status
    expr: source.entitlement_status
  - name: audit_run_id
    expr: source.audit_run_id
measures:
  - name: shift_count
    expr: COUNT(1)
  - name: worked_hours
    expr: SUM(COALESCE(source.worked_hours,0))
  - name: expected_entitlement
    expr: SUM(COALESCE(source.expected_amount,0))
  - name: review_shift_count
    expr: SUM(CASE WHEN source.entitlement_status = 'REQUIRES_REVIEW' OR source.review_flags IS NOT NULL THEN 1 ELSE 0 END)
'''
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`semantic`.`audit_detail` WITH METRICS LANGUAGE YAML AS $$\n{detail_yaml}\n$$''')

    rest_yaml = f'''version: 1.1
comment: "AuditHero governed rest-between-work findings from the latest successful audit runs"
source: {catalog}.gold.v_rest_break_findings_latest
fields:
  - name: employee_id
    expr: source.employee_id
  - name: employee_name
    expr: source.employee_name
  - name: finding_type
    expr: source.finding_type
  - name: previous_shift_end
    expr: source.previous_shift_end
  - name: next_shift_start
    expr: source.next_shift_start
  - name: required_rest_hours
    expr: source.required_rest_hours
  - name: actual_rest_hours
    expr: source.actual_rest_hours
  - name: rest_shortfall_hours
    expr: source.rest_shortfall_hours
  - name: status
    expr: source.status
  - name: payment_status
    expr: source.payment_status
  - name: overtime_rest_rule_applies
    expr: source.overtime_rest_rule_applies
  - name: audit_run_id
    expr: source.audit_run_id
measures:
  - name: rest_intervals
    expr: COUNT(1)
  - name: short_rest_findings
    expr: SUM(CASE WHEN COALESCE(source.rest_shortfall_hours,0) > 0 THEN 1 ELSE 0 END)
  - name: review_findings
    expr: SUM(CASE WHEN source.status = 'REQUIRES_REVIEW' THEN 1 ELSE 0 END)
  - name: overtime_rest_cases
    expr: SUM(CASE WHEN source.overtime_rest_rule_applies THEN 1 ELSE 0 END)
  - name: double_time_topup
    expr: SUM(COALESCE(source.double_time_topup,0))
'''
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`semantic`.`rest_break_compliance` WITH METRICS LANGUAGE YAML AS $$\n{rest_yaml}\n$$''')

    scenario_yaml = f'''version: 1.1
comment: "Selectable SCHADS classification and employment-type scenario calculations. Filter to the intended scenario before interpreting totals."
source: {catalog}.gold.v_award_scenario_detail_latest
fields:
  - name: employee_id
    expr: source.employee_id
  - name: employee_name
    expr: source.employee_name
  - name: shift_start
    expr: source.shift_start
  - name: classification_family
    expr: source.classification_family
  - name: classification_code
    expr: source.scenario_classification_code
  - name: classification_level
    expr: source.scenario_level
  - name: pay_point
    expr: source.scenario_pay_point
  - name: employment_type
    expr: source.scenario_employment_type
  - name: scenario_status
    expr: source.scenario_status
measures:
  - name: scenario_shift_rows
    expr: COUNT(1)
  - name: expected_pay
    expr: SUM(COALESCE(source.expected_amount,0))
  - name: observed_shift_pay
    expr: SUM(COALESCE(source.observed_shift_pay,0))
  - name: base_rate_shortfall
    expr: SUM(CASE WHEN source.base_rate_variance < 0 THEN -source.base_rate_variance * COALESCE(source.worked_hours,0) ELSE 0 END)
  - name: scenario_underpayment
    expr: SUM(CASE WHEN source.scenario_status='UNDERPAID' THEN GREATEST(-COALESCE(source.shift_variance_actual_minus_expected,0),0) ELSE 0 END)
  - name: scenario_overpayment
    expr: SUM(CASE WHEN source.scenario_status='OVERPAID' THEN GREATEST(COALESCE(source.shift_variance_actual_minus_expected,0),0) ELSE 0 END)
'''
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`semantic`.`award_scenarios` WITH METRICS LANGUAGE YAML AS $$\n{scenario_yaml}\n$$''')
