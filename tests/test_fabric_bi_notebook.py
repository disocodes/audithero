from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
BUILD_BI = ROOT / "fabric" / "notebooks" / "06_build_bi.py"


def test_fabric_build_bi_notebook_is_valid_python_source():
    text = BUILD_BI.read_text(encoding="utf-8")
    ast.parse(text, filename=str(BUILD_BI))


def test_fabric_build_bi_returns_structured_failure_details():
    text = BUILD_BI.read_text(encoding="utf-8")
    assert "AUDITHERO BUILD BI FAILED" in text
    assert "AUDITHERO_ERROR:" in text
    assert '"stage": stage' in text
    assert '"exception_type"' in text
    assert "traceback.format_exc" in text


def test_fabric_build_bi_exposes_semantic_link_runtime_contract():
    text = BUILD_BI.read_text(encoding="utf-8")
    assert 'version("semantic-link-labs")' in text
    assert "inspect.signature(generate_direct_lake_semantic_model)" in text
    assert "Semantic Link Labs version:" in text
    assert "generate_direct_lake_semantic_model signature:" in text


def test_fabric_build_bi_names_each_external_api_stage():
    text = BUILD_BI.read_text(encoding="utf-8")
    for stage in (
        "STEP 2 — Create/refresh the Direct Lake semantic model",
        "STEP 3 — Define payroll/audit business measures",
        "STEP 4 — Create or update the Power BI report",
        "STEP 4B — Rebind report to the AuditHero semantic model",
        "STEP 5 — Check Direct Lake fallback state",
    ):
        assert stage in text


def test_fabric_build_bi_uses_semantic_link_tom_wrapper_for_measures():
    text = BUILD_BI.read_text(encoding="utf-8")
    assert "import Microsoft.AnalysisServices.Tabular" not in text
    assert "tom.add_measure(" in text
    assert "TOM.Measure()" not in text
    assert "inspect.signature(tom.add_measure)" in text
