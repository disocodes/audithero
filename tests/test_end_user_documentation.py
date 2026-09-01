from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# These phrases indicate internal design/chat discussion rather than product documentation.
# Keep this list deliberately specific so normal instructional language remains valid.
FORBIDDEN_PHRASES = (
    "this chat",
    "our chat",
    "our conversation",
    "from the conversation",
    "as discussed",
    "as we discussed",
    "we decided",
    "we agreed",
    "you asked",
    "the user asked",
    "user requested",
    "i think we",
    "i would recommend",
    "my recommendation",
    "internal note",
    "internal discussion",
    "design discussion",
    "for context from",
)


def end_user_text_files():
    files = [ROOT / "README.md", ROOT / "QUICKSTART.md"]
    files.extend(sorted((ROOT / "docs").glob("*.md")))
    files.extend(sorted((ROOT / "databricks").rglob("*.md")))
    files.extend(sorted((ROOT / "fabric").rglob("*.md")))
    files.extend(sorted((ROOT / "notebooks").glob("*.py")))
    files.extend(sorted((ROOT / "fabric" / "notebooks").glob("*.py")))
    files.extend(sorted((ROOT / "installers").glob("*.py")))
    return [p for p in files if p.exists()]


def test_end_user_material_does_not_contain_chat_or_internal_discussion_language():
    offenders = []
    for path in end_user_text_files():
        text = path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                offenders.append(f"{path.relative_to(ROOT)}: {phrase!r}")
    assert not offenders, "End-user material contains internal discussion language:\n" + "\n".join(offenders)


def test_databricks_operator_docs_use_current_operating_surfaces():
    readme = (ROOT / "databricks" / "README.md").read_text(encoding="utf-8")
    install = (ROOT / "docs" / "INSTALL_DATABRICKS_UI.md").read_text(encoding="utf-8")

    for text in (readme, install):
        assert "Jobs & Pipelines" in text
        assert "Catalog Explorer" in text
        assert "AI/BI" in text
        assert "Genie" in text
        assert "/Volumes/schads_payroll/bronze/landing/import/raw" in text

    assert "No separate application is required" in readme


def test_databricks_setup_notebook_is_operator_facing():
    setup = (ROOT / "notebooks" / "00_setup.py").read_text(encoding="utf-8")
    mapping = (ROOT / "notebooks" / "02d_source_mapping_draft.py").read_text(encoding="utf-8")
    audit = (ROOT / "notebooks" / "03b_manual_file_audit.py").read_text(encoding="utf-8")

    assert "# MAGIC # AuditHero — Setup" in setup
    assert "Setup does not read employee payroll data" in setup
    assert "# MAGIC # AuditHero — Build a Source Mapping Workbook" in mapping
    assert "No payroll calculations are performed" in mapping
    assert "# MAGIC # AuditHero — Audit Uploaded CSV / Excel" in audit
    assert "NEXT:" in mapping
    assert "NEXT:" in audit
