from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABRICKS_YML = ROOT / "databricks.yml"
JOBS = ROOT / "resources" / "jobs.yml"
SETUP = ROOT / "notebooks" / "00_setup.py"
GENIE_SETUP = ROOT / "notebooks" / "00c_setup_genie.py"
DB_IO = ROOT / "src" / "schads_audit" / "databricks_io.py"
FILE_AUDIT = ROOT / "notebooks" / "03b_manual_file_audit.py"


def test_databricks_bundle_uses_direct_engine_for_modern_resources():
    text = DATABRICKS_YML.read_text(encoding="utf-8")
    assert "engine: direct" in text
    assert "databricks_cli_version: '>= 1.3.0'" in text


def test_setup_creates_semantic_schema_metric_views_and_genie():
    io_text = DB_IO.read_text(encoding="utf-8")
    setup_text = SETUP.read_text(encoding="utf-8")

    assert "'semantic'" in io_text
    assert "WITH METRICS LANGUAGE YAML" in io_text
    assert "semantic`.`payroll_compliance" in io_text
    assert "semantic`.`audit_detail" in io_text
    assert "create_metric_views(spark, catalog)" in setup_text
    assert 'dbutils.notebook.run(' in setup_text
    assert '"./00c_setup_genie"' in setup_text
    assert "from pathlib import Path" in setup_text


def test_genie_is_governed_by_gold_and_semantic_assets_only():
    text = GENIE_SETUP.read_text(encoding="utf-8")
    assert '"/api/2.0/genie/spaces"' in text
    assert "semantic.payroll_compliance" in text
    assert "semantic.audit_detail" in text
    assert "v_readiness_findings" in text
    assert "v_rule_coverage" in text
    assert "Never treat REQUIRES_REVIEW as an underpayment" in text
    assert "Do not query Bronze or Silver assets" in text


def test_operator_jobs_have_real_unity_catalog_volume_defaults():
    text = JOBS.read_text(encoding="utf-8")
    assert 'default: "/Volumes/${var.catalog}/bronze/landing/import/raw"' in text
    assert 'default: "/Volumes/${var.catalog}/bronze/landing/import/source_mapping.xlsx"' in text
    assert 'default: "/Volumes/${var.catalog}/bronze/landing/input"' in text
    assert 'name: "AuditHero - Convert Mapped Files and Run Audit"' in text


def test_uploaded_file_audit_persists_normalized_and_audit_data():
    text = FILE_AUDIT.read_text(encoding="utf-8")
    assert 'f"{catalog}.silver.{name}"' in text
    assert 'f"{catalog}.gold.audit_detail"' in text
    assert 'f"{catalog}.gold.pay_period_reconciliation"' in text
    assert 'f"{catalog}.ops.audit_runs"' in text
