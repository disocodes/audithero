import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_contains_live_data_widgets():
    dashboard = json.loads((ROOT / "dashboard" / "payroll_compliance.lvdash.json").read_text(encoding="utf-8"))

    datasets = {item["name"]: item for item in dashboard["datasets"]}
    assert {"kpi", "status_summary", "exceptions", "detail", "runs", "readiness", "rules"}.issubset(datasets)
    assert all(isinstance(item.get("queryLines"), list) and item["queryLines"] for item in dashboard["datasets"])
    assert all("query" not in item for item in dashboard["datasets"])

    pages = {page["name"]: page for page in dashboard["pages"]}
    assert {"overview", "exceptions", "evidence", "controls"}.issubset(pages)

    overview_types = {
        widget.get("widget", {}).get("spec", {}).get("widgetType")
        for widget in pages["overview"]["layout"]
        if widget.get("widget", {}).get("spec")
    }
    assert "counter" in overview_types
    assert "bar" in overview_types
    assert "table" in overview_types

    for page_name in ("exceptions", "evidence", "controls"):
        assert any(
            item.get("widget", {}).get("queries")
            for item in pages[page_name]["layout"]
        ), f"{page_name} must contain at least one dataset-backed widget"

    dataset_names = set(datasets)
    for page in dashboard["pages"]:
        for item in page.get("layout", []):
            for query in item.get("widget", {}).get("queries", []):
                assert query["query"]["datasetName"] in dataset_names


def test_setup_verifies_and_republishes_dashboard():
    jobs = (ROOT / "resources" / "jobs.yml").read_text(encoding="utf-8")
    verifier = (ROOT / "notebooks" / "00d_verify_dashboard.py").read_text(encoding="utf-8")

    assert "task_key: verify_dashboard" in jobs
    assert "../notebooks/00d_verify_dashboard.py" in jobs
    assert 'current = call("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}")' in verifier
    assert '"PATCH"' in verifier
    assert 'f"/api/2.0/lakeview/dashboards/{dashboard_id}/published"' in verifier
    assert "Databricks did not retain the AuditHero dashboard definition" in verifier


def test_reporting_views_choose_latest_successful_run_before_ranking():
    source = (ROOT / "src" / "schads_audit" / "databricks_io.py").read_text(encoding="utf-8")
    statement = next(
        line for line in source.splitlines()
        if "v_latest_audit_runs" in line and "CREATE OR REPLACE VIEW" in line
    )
    assert "WHERE status='SUCCESS' QUALIFY ROW_NUMBER()" in statement
    assert "PARTITION BY audit_window_start,audit_window_end" in statement
