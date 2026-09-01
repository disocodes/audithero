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


def test_databricks_notebooks_have_end_user_title_and_purpose():
    for path in sorted((ROOT / "notebooks").glob("*.py")):
        if path.name == "_common.py":
            continue
        text = path.read_text(encoding="utf-8")
        opening = "\n".join(text.splitlines()[:20])
        assert "# MAGIC # AuditHero —" in opening, f"Missing AuditHero title: {path.name}"
        assert "**Purpose:**" in opening, f"Missing end-user purpose: {path.name}"


def test_fabric_notebooks_have_end_user_title_and_purpose():
    for path in sorted((ROOT / "fabric" / "notebooks").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        opening = "\n".join(text.splitlines()[:24])
        assert "AuditHero" in opening, f"Missing AuditHero title: {path.name}"
        assert "PURPOSE" in opening, f"Missing end-user PURPOSE section: {path.name}"


def test_key_operator_notebooks_include_next_step_guidance():
    mapping = (ROOT / "notebooks" / "02d_source_mapping_draft.py").read_text(encoding="utf-8")
    conversion = (ROOT / "notebooks" / "02e_convert_source_files.py").read_text(encoding="utf-8")
    readiness = (ROOT / "notebooks" / "02c_file_readiness.py").read_text(encoding="utf-8")
    audit = (ROOT / "notebooks" / "03b_manual_file_audit.py").read_text(encoding="utf-8")

    assert "NEXT:" in mapping
    assert "NEXT:" in conversion
    assert "NEXT:" in readiness
    assert "NEXT:" in audit
