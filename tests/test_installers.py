from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

INSTALLERS = {
    "fabric_install": ROOT / "installers" / "Fabric_Install_AuditHero.py",
    "fabric_uninstall": ROOT / "installers" / "Fabric_Uninstall_AuditHero.py",
    "databricks_install": ROOT / "installers" / "Databricks_Install_AuditHero.py",
    "databricks_uninstall": ROOT / "installers" / "Databricks_Uninstall_AuditHero.py",
}


def source(name: str) -> str:
    return INSTALLERS[name].read_text(encoding="utf-8")


def test_all_installers_are_valid_python_sources():
    for name, path in INSTALLERS.items():
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_fabric_deployer_is_valid_python_source():
    path = ROOT / "fabric" / "scripts" / "deploy_fabric.py"
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_fabric_runtime_initializer_is_valid_python_source():
    path = ROOT / "fabric" / "scripts" / "run_fabric_initialization.py"
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_installers_default_to_preserving_optional_credentials_and_schedules():
    fabric = source("fabric_install")
    assert 'key_vault_url = ""' in fabric
    assert "monthly_schedule_enabled = False" in fabric

    databricks = source("databricks_install")
    assert 'sql_warehouse_id = ""' in databricks
    assert 'existing_cluster_id = ""' in databricks


def test_databricks_installer_uses_current_jobs_api_and_publishes_dashboard():
    databricks = source("databricks_install")
    assert "/api/2.2/jobs/list" in databricks
    assert "/api/2.2/jobs/create" in databricks
    assert "/api/2.2/jobs/reset" in databricks
    assert "/api/2.2/jobs/run-now" in databricks
    assert "/api/2.2/jobs/runs/get" in databricks
    assert "/published" in databricks
    assert '"embed_credentials": False' in databricks


def test_installers_create_the_mapped_file_operator_path():
    fabric = source("fabric_install")
    databricks = source("databricks_install")
    assert "deploy_source_mapping.py" in fabric
    assert "AuditHero - Convert Mapped Files and Run Audit" in fabric
    assert "resources" in databricks and "jobs.yml" in databricks
    assert "AuditHero - Convert Mapped Files and Run Audit" in databricks


def test_fabric_installer_surfaces_child_deployer_errors():
    fabric = source("fabric_install")
    assert "subprocess.Popen" in fabric
    assert "stderr=subprocess.STDOUT" in fabric
    assert "AuditHero installer step" in fabric
    assert "CalledProcessError" in fabric


def test_fabric_installer_isolates_bootstrap_dependencies_from_managed_runtime():
    fabric = source("fabric_install")
    assert "bootstrap_deps" in fabric
    assert '"--ignore-installed"' in fabric
    assert '"--target"' in fabric
    assert 'child_env["PYTHONPATH"]' in fabric
    assert "env=child_env" in fabric


def test_fabric_installer_separates_resource_deployment_from_spark_initialization():
    fabric = source("fabric_install")
    assert "run_fabric_initialization.py" in fabric
    assert 'command.append("--skip-run")' in fabric
    assert "deploy_fabric.py" in fabric

    runtime = (ROOT / "fabric" / "scripts" / "run_fabric_initialization.py").read_text(
        encoding="utf-8"
    )
    assert "/jobs/execute/instances?jobType=RunNotebook" in runtime
    assert "exitValue" in runtime
    assert "AUDITHERO_ERROR:" in runtime
    assert "defaultLakehouse" in runtime
    assert "attachedEnvironment" in runtime


def test_fabric_runtime_verifies_and_repairs_published_custom_wheel():
    runtime = (ROOT / "fabric" / "scripts" / "run_fabric_initialization.py").read_text(
        encoding="utf-8"
    )
    assert "/libraries?beta=false" in runtime
    assert "/staging/libraries/{quote(wheel_path.name, safe='')}" in runtime
    assert '"Content-Type": "application/octet-stream"' in runtime
    assert "/staging/publish?beta=false" in runtime
    assert "Published custom library verified" in runtime
    assert "ensure_audithero_wheel(environment_id)" in runtime


def test_fabric_setup_returns_structured_failure_details():
    setup = (ROOT / "fabric" / "notebooks" / "00_setup.py").read_text(
        encoding="utf-8"
    )
    assert "AUDITHERO_ERROR:" in setup
    assert '"stage": stage' in setup
    assert '"exception_type"' in setup
    assert "traceback.format_exc" in setup


def test_fabric_spark_sql_helpers_name_failing_operations_and_avoid_shortcuts():
    io = (ROOT / "src" / "schads_audit" / "fabric_io.py").read_text(
        encoding="utf-8"
    )
    assert "Fabric Spark SQL failed while" in io
    assert "QUALIFY ROW_NUMBER" not in io
    assert "GROUP BY ALL" not in io


def test_fabric_notebook_updates_do_not_request_platform_metadata_without_platform_file():
    deployer = (ROOT / "fabric" / "scripts" / "deploy_fabric.py").read_text(
        encoding="utf-8"
    )
    assert "updateDefinition?updateMetadata=true" not in deployer
    assert "notebook-content.py" in deployer


def test_fabric_pipeline_schedule_uses_workload_specific_execute_endpoint():
    deployer = (ROOT / "fabric" / "scripts" / "deploy_fabric.py").read_text(
        encoding="utf-8"
    )
    assert "/dataPipelines/{pipeline_id}" in deployer
    assert '"/jobs/execute/schedules"' in deployer
    assert "/jobs/DefaultJob/schedules" not in deployer


def test_fabric_waits_for_environment_publish_before_notebook_runs():
    deployer = (ROOT / "fabric" / "scripts" / "deploy_fabric.py").read_text(
        encoding="utf-8"
    )
    assert "wait_environment_publish" in deployer
    assert "publishDetails" in deployer
    assert 'state == "success"' in deployer
    assert "/staging/publish?beta=false" in deployer


def test_fabric_notebook_runs_use_explicit_compute_bindings_and_diagnostics():
    deployer = (ROOT / "fabric" / "scripts" / "deploy_fabric.py").read_text(
        encoding="utf-8"
    )
    assert "/jobs/execute/instances?beta=false" in deployer
    assert "defaultLakehouse" in deployer
    assert "attachedEnvironment" in deployer
    assert "executionSnapshotUrl" in deployer
    assert "driverLogUrl" in deployer
    assert "sparkJobDetailsUrl" in deployer


def test_uninstallers_require_explicit_confirmation_for_data_deletion():
    for name in ("fabric_uninstall", "databricks_uninstall"):
        text = source(name)
        assert "delete_audit_data = False" in text
        assert 'confirmation = ""' in text
        assert 'confirmation != "DELETE AUDITHERO DATA"' in text


def test_databricks_uninstaller_only_removes_installer_created_warehouse():
    text = source("databricks_uninstall")
    assert 'state.get("warehouse_created_by_installer")' in text
    assert "/api/2.2/jobs/delete" in text


def test_fabric_bootstrap_uses_notebook_identity_for_fabric_api():
    install = source("fabric_install")
    uninstall = source("fabric_uninstall")
    assert 'notebookutils.credentials.getToken("pbi")' in install
    assert 'notebookutils.credentials.getToken("pbi")' in uninstall
