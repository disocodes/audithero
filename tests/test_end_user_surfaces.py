from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_MARKDOWN = [
    ROOT / "README.md",
    ROOT / "QUICKSTART.md",
    *sorted((ROOT / "docs").glob("*.md")),
    ROOT / "fabric" / "README.md",
    ROOT / "databricks" / "README.md",
    ROOT / "databricks" / "docs" / "README.md",
]

PUBLIC_NOTEBOOKS = [
    *sorted((ROOT / "notebooks").glob("*.py")),
    *sorted((ROOT / "fabric" / "notebooks").glob("*.py")),
    ROOT / "installers" / "Fabric_Install_AuditHero.py",
    ROOT / "installers" / "Fabric_Uninstall_AuditHero.py",
    ROOT / "installers" / "Databricks_Install_AuditHero.py",
    ROOT / "installers" / "Databricks_Uninstall_AuditHero.py",
]

CHAT_OR_DEBUG_RESIDUE = (
    "there is no separate app",
    "no separate audithero application is required",
    "normal payroll users",
    "normal payroll operators",
    "normal operators do not",
    "this is intentional:",
    "a later setup/self test/bi failure must never",
    "fabric does not hide the underlying error",
    "normalized legacy fabric lakehouse path",
    "environment changes only take effect",
    "this is the normal first-run state",
    "as discussed",
    "you asked",
    "from this chat",
    "we decided",
    "not full time / part time / casual",
    "tom add_measure signature:",
    "generate_direct_lake_semantic_model signature:",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_docs_and_notebooks_do_not_contain_chat_or_debug_residue():
    for path in [*PUBLIC_MARKDOWN, *PUBLIC_NOTEBOOKS]:
        text = _text(path).lower()
        for phrase in CHAT_OR_DEBUG_RESIDUE:
            assert phrase not in text, f"{path.relative_to(ROOT)} contains internal wording: {phrase}"


def test_databricks_notebooks_import_path_before_using_path_cwd():
    for path in sorted((ROOT / "notebooks").glob("*.py")):
        text = _text(path)
        if "Path.cwd()" not in text:
            continue
        import_pos = text.find("from pathlib import Path")
        use_pos = text.find("Path.cwd()")
        assert import_pos >= 0, f"{path.name} uses Path without importing it"
        assert import_pos < use_pos, f"{path.name} imports Path after first use"


def test_mapping_notebooks_point_to_combined_operator_workflow():
    for path in (
        ROOT / "notebooks" / "02d_source_mapping_draft.py",
        ROOT / "fabric" / "notebooks" / "03c_source_mapping_draft.py",
    ):
        text = _text(path)
        assert "AuditHero - Convert Mapped Files and Run Audit" in text
        assert "conversion and File Readiness" in text


def test_databricks_mapping_workbook_is_published_without_dbutils_tmp_access():
    text = _text(ROOT / "notebooks" / "02d_source_mapping_draft.py")
    assert "tempfile.mkdtemp" in text
    assert "write_mapping_workbook(mapping, local_file)" in text
    assert "shutil.copyfile(local_file, destination)" in text
    assert "dbutils.fs.cp(local_file.as_uri()" not in text
    assert "dbfs:{path}" in text


def test_databricks_conversion_stages_generated_files_before_volume_publish():
    text = _text(ROOT / "notebooks" / "02e_convert_source_files.py")
    assert "audithero-convert-" in text
    assert "conversion_output_root" in text
    assert "_publish_staged_files" in text
    assert "shutil.copyfile(source_file, target_root / source_file.name)" in text
    assert "assess_file_readiness(output_root, output_root)" in text


def test_databricks_pay_category_treatment_is_explicit_and_complete():
    mapping = _text(ROOT / "notebooks" / "02d_source_mapping_draft.py")
    conversion = _text(ROOT / "notebooks" / "02e_convert_source_files.py")
    assert "pay_category_treatment" in mapping
    assert '"AUDITABLE_WORK,ALLOWANCE,EXCLUDE"' in mapping
    assert "Suggested treatments are guidance only" in mapping
    assert 'draft["datasets"]["pay_category_mapping"]["enabled"] = False' in mapping
    assert "same source column as employee_id" in mapping
    assert "pay_category_treatment" in conversion
    assert "Complete the pay_category_treatment sheet before conversion" in conversion
    assert "pay_category_mapping.csv" in conversion
    assert "does not cover all pay categories present in payroll earnings" in conversion


def test_fabric_pay_category_treatment_matches_databricks_control():
    mapping = _text(ROOT / "fabric" / "notebooks" / "03c_source_mapping_draft.py")
    conversion = _text(ROOT / "fabric" / "notebooks" / "03d_convert_source_files.py")
    assert "pay_category_treatment" in mapping
    assert '"AUDITABLE_WORK,ALLOWANCE,EXCLUDE"' in mapping
    assert "same source column as employee_id" in mapping
    assert 'draft["datasets"]["pay_category_mapping"]["enabled"] = False' in mapping
    assert "pay_category_treatment" in conversion
    assert "Complete the pay_category_treatment sheet before conversion" in conversion
    assert "pay_category_mapping.csv" in conversion
    assert "does not cover all pay categories present in payroll earnings" in conversion
    assert 'mapping["datasets"]["pay_category_mapping"]["enabled"] = False' in conversion


def test_readiness_success_messages_do_not_report_blocking_items_present():
    for path in (
        ROOT / "notebooks" / "02b_audit_readiness.py",
        ROOT / "fabric" / "notebooks" / "03_readiness.py",
    ):
        text = _text(path)
        assert "No blocking mapping/register findings remain" in text
        assert "Blocking mappings/registers are present" not in text


def test_databricks_end_user_docs_name_current_reporting_surfaces():
    for path in (
        ROOT / "README.md",
        ROOT / "databricks" / "README.md",
        ROOT / "docs" / "INSTALL_DATABRICKS_UI.md",
    ):
        text = _text(path)
        assert "AuditHero - SCHADS Payroll Compliance" in text
        assert "AuditHero - Payroll Compliance" in text
        assert "Genie" in text
