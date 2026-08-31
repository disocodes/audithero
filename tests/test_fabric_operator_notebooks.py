from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installers" / "Fabric_Install_AuditHero.py"
MAPPING_DRAFT = ROOT / "fabric" / "notebooks" / "03c_source_mapping_draft.py"
MAPPING_CONVERT = ROOT / "fabric" / "notebooks" / "03d_convert_source_files.py"


def test_fabric_operator_notebooks_deploy_before_runtime_validation():
    text = INSTALLER.read_text(encoding="utf-8")
    deploy_fabric = text.index('repo_root / "fabric" / "scripts" / "deploy_fabric.py"', text.index("steps = ["))
    deploy_file_source = text.index('repo_root / "fabric" / "scripts" / "deploy_file_source.py"', deploy_fabric)
    deploy_source_mapping = text.index('repo_root / "fabric" / "scripts" / "deploy_source_mapping.py"', deploy_file_source)
    deploy_admin = text.index('repo_root / "fabric" / "scripts" / "deploy_admin_notebooks.py"', deploy_source_mapping)
    runtime_init = text.index('repo_root / "fabric" / "scripts" / "run_fabric_initialization.py"', deploy_admin)

    assert deploy_fabric < deploy_file_source < deploy_source_mapping < deploy_admin < runtime_init
    assert "a later Setup/Self Test/BI failure must never leave the operator" in text


def test_fabric_source_mapping_notebooks_explain_stale_environment_sessions():
    for path in (MAPPING_DRAFT, MAPPING_CONVERT):
        text = path.read_text(encoding="utf-8")
        assert 'except ModuleNotFoundError as exc:' in text
        assert 'AuditHero_Environment' in text
        assert 'stop the current session and start a new one' in text
        assert 'environment changes' in text
