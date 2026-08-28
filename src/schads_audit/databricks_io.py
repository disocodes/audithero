import json
import pandas as pd


def create_catalog_objects(spark, catalog):
    spark.sql(f'CREATE CATALOG IF NOT EXISTS `{catalog}`')
    for schema in ('bronze','silver','ref','gold','ops'):
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
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_latest_audit_runs` AS SELECT * FROM `{catalog}`.`ops`.`audit_runs` QUALIFY ROW_NUMBER() OVER (PARTITION BY audit_window_start,audit_window_end ORDER BY finished_at DESC)=1''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_audit_detail_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`audit_detail` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id WHERE r.status='SUCCESS' ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_event_adjustments_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`audit_event_adjustments` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id WHERE r.status='SUCCESS' ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_toil_findings_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`toil_findings` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id WHERE r.status='SUCCESS' ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_reconciliation_latest` AS SELECT d.* FROM `{catalog}`.`gold`.`pay_period_reconciliation` d JOIN `{catalog}`.`gold`.`v_latest_audit_runs` r ON d.audit_run_id=r.audit_run_id WHERE r.status='SUCCESS' ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_rule_coverage` AS SELECT * FROM `{catalog}`.`ref`.`rule_coverage` ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_audit_runs` AS SELECT * FROM `{catalog}`.`ops`.`audit_runs` ''')
    spark.sql(f'''CREATE OR REPLACE VIEW `{catalog}`.`gold`.`v_readiness_findings` AS SELECT * FROM `{catalog}`.`ops`.`readiness_findings` ''')
