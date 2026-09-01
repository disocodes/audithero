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
    assert "Deploy managed workspace resources before running the installation validation sequence" in text


def test_fabric_source_mapping_notebooks_explain_environment_requirement():
    for path in (MAPPING_DRAFT, MAPPING_CONVERT):
        text = path.read_text(encoding="utf-8")
        assert 'except ModuleNotFoundError as exc:' in text
        assert 'AuditHero_Environment' in text
        assert 'start a new Spark session' in text


def test_fabric_source_mapping_notebooks_normalize_lakehouse_mounts():
    for path in (MAPPING_DRAFT, MAPPING_CONVERT):
        text = path.read_text(encoding="utf-8")
        assert "_normalize_fabric_lakehouse_path" in text
        assert '("/lakehouse/Files", "/lakehouse/default/Files")' in text
        assert '("/lakehouse/Tables", "/lakehouse/default/Tables")' in text
        assert "Normalized Fabric Lakehouse path:" in text


def test_fabric_mapping_draft_creates_operator_upload_folder_before_scan():
    text = MAPPING_DRAFT.read_text(encoding="utf-8")
    mkdir_pos = text.index("source_dir.mkdir(parents=True, exist_ok=True)")
    scan_pos = text.index("inventory = scan_source_items(source_root)")
    assert mkdir_pos < scan_pos
    assert "Upload the payroll, HR, roster or timekeeping exports" in text


def test_fabric_mapping_draft_points_to_combined_audit_workflow():
    text = MAPPING_DRAFT.read_text(encoding="utf-8")
    assert "NEXT: run 'AuditHero - Convert Mapped Files and Run Audit'." in text
    assert "conversion and File Readiness need to be checked without running the payroll audit" in text
