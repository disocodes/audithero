from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_STAGES = ['apply_broken_shift_rules','apply_sleepover_group_rules','apply_rostered_and_daily_overtime','allocate_period_overtime','apply_part_time_pattern_checks','apply_meal_break_events','apply_rest_after_overtime','apply_instrument_history','aggregate_remote_work_events','calculate_supplemental_events','audit_toil_register','reconcile_pay_periods']

def _text(path):
    return (ROOT / path).read_text(encoding='utf-8')

def test_fabric_and_databricks_execute_same_compliance_stages():
    fabric=_text('src/schads_audit/fabric_pipeline.py')
    databricks=_text('src/schads_audit/databricks_pipeline_v2.py')
    for stage in SHARED_STAGES:
        assert stage in fabric, f'Fabric missing {stage}'
        assert stage in databricks, f'Databricks missing {stage}'

def test_canonical_databricks_jobs_use_complete_engine():
    assert 'run_databricks_audit_v2' in _text('notebooks/03_historical_audit.py')
    assert 'run_databricks_audit_v2' in _text('notebooks/04_monthly_payroll_audit.py')
    jobs=_text('resources/jobs.yml')
    assert '03_historical_audit.py' in jobs and '04_monthly_payroll_audit.py' in jobs
    assert '10_historical_audit_complete.py' not in jobs

def test_fabric_successful_runs_publish_direct_lake_snapshots():
    assert 'publish_current_snapshots' in _text('fabric/notebooks/04_historical_audit.py')
    assert 'publish_current_snapshots' in _text('fabric/notebooks/05_monthly_audit.py')
    assert 'ensure_current_tables' in _text('fabric/notebooks/00_setup.py')

def test_one_canonical_fabric_installer():
    deploy=_text('fabric/scripts/deploy.sh')
    assert 'deploy_fabric.py' in deploy
    assert 'deploy_fabric_complete.py' not in deploy
    assert 'deploy_fabric_final.py' not in deploy
