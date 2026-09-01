import json
import pandas as pd


def create_catalog_objects(spark, catalog):
    spark.sql(f'CREATE CATALOG IF NOT EXISTS `{catalog}`')
    for schema in ('bronze','silver','ref','gold','ops','semantic'):
        spark.sql(f'CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`')
    spark.sql(f'CREATE VOLUME IF NOT EXISTS `{catalog}`.`bronze`.`landing`')


def write_df(spark, df, table, mode='append'):
    if df is None or df.empty:
        return
    spark.createDataFrame(df.where(pd.notna(df), None)).write.format('delta').mode(mode).option('mergeSchema','true').saveAsTable(table)


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
    # Reporting views always retain the latest successful audit for each window.
    # A later failed attempt remains visible in v_audit_runs but must not hide the
    # previous successful Gold snapshot.
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_latest_audit_runs` AS SELECT * FROM `{catalog}`.`ops`.`audit_runs` WHERE status='SUCCESS' QUALIFY ROW_NUMBER() OVER (PARTITION BY audit_window_start,audit_window_end ORDER BY finished_at DESC)=1''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_audit_detail_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`audit_detail` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_event_adjustments_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`audit_event_adjustments` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_toil_findings_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`toil_findings` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_reconciliation_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`pay_period_reconciliation` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_rule_coverage` AS SELECT * FROM `{catalog}`.`ref`.`rule_coverage` ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_audit_runs` AS SELECT * FROM `{catalog}`.`ops`.`audit_runs` ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_readiness_findings` AS SELECT * FROM `{catalog}`.`ops`.`readiness_findings` ''')


def create_metric_views(spark, catalog):
    """Create the governed Unity Catalog semantic layer consumed by AI/BI and Genie."""
    payroll_yaml = f'''version: 1.1
comment: "AuditHero governed payroll compliance metrics from the latest successful audit runs"
source: {catalog}.gold.v_reconciliation_latest
fields:
  - name: employee_id
    expr: source.employee_id
    comment: "Employee identifier"
  - name: employee_name
    expr: source.employee_name
    comment: "Employee name"
  - name: pay_period_start
    expr: source.pay_period_start
    comment: "Pay period start"
  - name: pay_period_end
    expr: source.pay_period_end
    comment: "Pay period end"
  - name: status
    expr: source.status
    comment: "AuditHero reconciliation status"
  - name: run_type
    expr: source.run_type
    comment: "Audit execution type"
  - name: audit_run_id
    expr: source.audit_run_id
    comment: "Immutable audit run identifier"
measures:
  - name: employee_count
    expr: COUNT(DISTINCT source.employee_id)
    comment: "Distinct employees represented in the selected audit results"
  - name: pay_period_count
    expr: COUNT(1)
    comment: "Audited employee pay periods"
  - name: expected_pay
    expr: SUM(COALESCE(source.expected_amount, 0))
    comment: "Total expected auditable pay calculated by AuditHero"
  - name: actual_pay
    expr: SUM(COALESCE(source.actual_auditable_amount, 0))
    comment: "Total actual auditable payroll amount supplied to AuditHero"
  - name: potential_underpayment
    expr: SUM(CASE WHEN source.status = 'UNDERPAID' THEN GREATEST(COALESCE(source.expected_amount,0) - COALESCE(source.actual_auditable_amount,0), 0) ELSE 0 END)
    comment: "Confirmed auditable shortfall for rows classified UNDERPAID; excludes REQUIRES_REVIEW"
  - name: potential_overpayment
    expr: SUM(CASE WHEN source.status = 'OVERPAID' THEN GREATEST(COALESCE(source.actual_auditable_amount,0) - COALESCE(source.expected_amount,0), 0) ELSE 0 END)
    comment: "Confirmed auditable excess for rows classified OVERPAID"
  - name: underpaid_periods
    expr: SUM(CASE WHEN source.status = 'UNDERPAID' THEN 1 ELSE 0 END)
    comment: "Number of pay periods classified UNDERPAID"
  - name: overpaid_periods
    expr: SUM(CASE WHEN source.status = 'OVERPAID' THEN 1 ELSE 0 END)
    comment: "Number of pay periods classified OVERPAID"
  - name: review_periods
    expr: SUM(CASE WHEN source.status = 'REQUIRES_REVIEW' THEN 1 ELSE 0 END)
    comment: "Number of pay periods requiring human review"
  - name: compliant_periods
    expr: SUM(CASE WHEN source.status = 'COMPLIANT' THEN 1 ELSE 0 END)
    comment: "Number of compliant pay periods"
'''
    spark.sql(
        f'''CREATE OR REPLACE VIEW `{catalog}`.`semantic`.`payroll_compliance` WITH METRICS LANGUAGE YAML AS $$\n{payroll_yaml}\n$$'''
    )

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
    comment: "Number of shift-level audit records"
  - name: worked_hours
    expr: SUM(COALESCE(source.worked_hours,0))
    comment: "Total worked hours represented by the audit records"
  - name: expected_entitlement
    expr: SUM(COALESCE(source.expected_amount,0))
    comment: "Total expected shift-level entitlement"
  - name: review_shift_count
    expr: SUM(CASE WHEN source.entitlement_status = 'REQUIRES_REVIEW' OR source.review_flags IS NOT NULL THEN 1 ELSE 0 END)
    comment: "Shift records requiring review"
'''
    spark.sql(
        f'''CREATE OR REPLACE VIEW `{catalog}`.`semantic`.`audit_detail` WITH METRICS LANGUAGE YAML AS $$\n{detail_yaml}\n$$'''
    )
