import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_contains_live_data_widgets():
    dashboard = json.loads((ROOT / "dashboard" / "payroll_compliance.lvdash.json").read_text(encoding="utf-8"))

    datasets = {item["name"]: item for item in dashboard["datasets"]}
    assert {"kpi", "status_summary", "exceptions", "detail", "runs", "readiness", "rules"}.issubset(datasets)
    assert all("query" in item for item in dashboard["datasets"])
    assert all("queryLines" not in item for item in dashboard["datasets"])

    pages = {page["name"]: page for page in dashboard["pages"]}
    assert {"overview", "exceptions", "evidence", "supplemental", "controls"}.issubset(pages)

    overview_types = {
        widget.get("widget", {}).get("spec", {}).get("widgetType")
        for widget in pages["overview"]["layout"]
        if widget.get("widget", {}).get("spec")
    }
    assert "counter" in overview_types
    assert "bar" in overview_types
    assert "table" in overview_types

    for page_name in ("exceptions", "evidence", "supplemental", "controls"):
        assert any(
            item.get("widget", {}).get("queries")
            for item in pages[page_name]["layout"]
        ), f"{page_name} must contain at least one dataset-backed widget"


def test_reporting_views_choose_latest_successful_run_before_ranking():
    source = (ROOT / "src" / "schads_audit" / "databricks_io.py").read_text(encoding="utf-8")
    statement = next(
        line for line in source.splitlines()
        if "v_latest_audit_runs" in line and "CREATE OR REPLACE VIEW" in line
    )
    assert "WHERE status='SUCCESS' QUALIFY ROW_NUMBER()" in statement
    assert "PARTITION BY audit_window_start,audit_window_end" in statement
