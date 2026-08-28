from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_STAGES = [
    'apply_broken_shift_rules','apply_sleepover_group_rules',
    'apply_rostered_and_daily_overtime','allocate_period_overtime',
    'apply_part_time_pattern_checks','apply_meal_break_events',
    'apply_rest_after_overtime','apply_instrument_history',
    'aggregate_remote_work_events','calculate_supplemental_events',
    'audit_toil_register','reconcile_pay_periods'
]


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
    assert 'pause_status: PAUSED' in jobs


def test_fabric_successful_runs_publish_direct_lake_snapshots():
    assert 'publish_current_snapshots' in _text('fabric/notebooks/04_historical_audit.py')
    assert 'publish_current_snapshots' in _text('fabric/notebooks/05_monthly_audit.py')
    assert 'ensure_current_tables' in _text('fabric/notebooks/00_setup.py')


def test_one_canonical_fabric_installer():
    deploy=_text('fabric/scripts/deploy.sh')
    assert 'deploy_fabric.py' in deploy
    assert 'deploy_fabric_complete.py' not in deploy
    assert 'deploy_fabric_final.py' not in deploy


def test_both_platform_deployments_run_preflight():
    fabric=_text('fabric/scripts/deploy.sh')
    dbx=_text('scripts/deploy.sh')
    assert 'scripts/validate_repo.py' in fabric
    assert 'fabric/scripts/preflight.py' in fabric
    assert 'scripts/validate_repo.py' in dbx
    assert 'scripts/databricks_preflight.py' in dbx


def test_cross_platform_windows_entrypoints_exist():
    for path in (
        'fabric/scripts/deploy.ps1',
        'fabric/scripts/configure_key_vault.ps1',
        'scripts/deploy.ps1',
        'scripts/configure_secrets.ps1',
    ):
        assert (ROOT / path).exists(), path


def test_fabric_bi_dependency_and_runtime_guard_are_pinned():
    env=_text('fabric/environment/environment.yml')
    guard=_text('src/schads_audit/fabric_bi_preflight.py')
    notebook=_text('fabric/notebooks/06_build_bi.py')
    assert 'semantic-link-labs==0.17.0' in env
    assert 'EXPECTED_SEMANTIC_LINK_LABS_VERSION = "0.17.0"' in guard
    assert 'validate_fabric_bi_runtime' in notebook
    for name in (
        'generate_direct_lake_semantic_model',
        'create_report_from_reportjson',
        'update_report_from_reportjson',
        'report_rebind',
    ):
        assert name in guard


def test_monthly_schedules_default_safe():
    import json
    fabric=json.loads(_text('fabric/config/fabric.example.json'))
    assert fabric['monthly_schedule']['enabled'] is False
    assert 'pause_status: PAUSED' in _text('resources/jobs.yml')
