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
