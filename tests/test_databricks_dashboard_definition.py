import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _built_dashboard():
    builder_path = ROOT / "dashboard" / "lakeview_builder.py"
    module_spec = importlib.util.spec_from_file_location("audithero_lakeview_builder_test", builder_path)
    assert module_spec is not None and module_spec.loader is not None
    builder = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(builder)
    spec = json.loads((ROOT / "dashboard" / "payroll_compliance.spec.json").read_text(encoding="utf-8"))
    return builder.build_dashboard(spec)


def _page(dashboard, name):
    return next(page for page in dashboard["pages"] if page["name"] == name)


def _widgets(page):
    return [item.get("widget", {}) for item in page.get("layout", [])]


def test_dashboard_uses_one_investigation_dataset_for_linked_analysis():
    dashboard = _built_dashboard()
    datasets = {item["name"]: item for item in dashboard["datasets"]}

    assert {"investigation", "runs", "readiness", "rules"}.issubset(datasets)
    assert "v_audit_investigation_latest" in datasets["investigation"]["queryLines"][0]
    assert all(isinstance(item.get("queryLines"), list) and item["queryLines"] for item in dashboard["datasets"])

    for page_name in ("overview", "investigation"):
        for widget in _widgets(_page(dashboard, page_name)):
            for query in widget.get("queries", []):
                assert query["query"]["datasetName"] == "investigation"


def test_dashboard_has_current_field_filters_for_audit_investigation():
    dashboard = _built_dashboard()
    overview = _widgets(_page(dashboard, "overview"))
    investigation = _widgets(_page(dashboard, "investigation"))

    filter_widgets = [
        widget for widget in [*overview, *investigation]
        if str(widget.get("spec", {}).get("widgetType", "")).startswith("filter-")
    ]
    assert filter_widgets

    fields = {
        widget["spec"]["encodings"]["fields"][0]["fieldName"]
        for widget in filter_widgets
    }
    assert {
        "reconciliation_status",
        "employee_name",
        "employment_type",
        "classification_code",
        "work_group",
        "state",
        "employee_pay_period",
    }.issubset(fields)

    for widget in filter_widgets:
        assert widget["spec"]["version"] == 2
        assert widget["spec"]["frame"]["showTitle"] is True
        assert "associative_filter_predicate_group" not in json.dumps(widget)
        for query in widget["queries"]:
            assert query["query"]["disaggregated"] is False
            assert len(query["query"]["fields"]) == 1


def test_dashboard_contains_kpis_charts_and_searchable_detail_tables():
    dashboard = _built_dashboard()
    overview = _widgets(_page(dashboard, "overview"))
    investigation = _widgets(_page(dashboard, "investigation"))

    overview_types = {widget.get("spec", {}).get("widgetType") for widget in overview}
    investigation_types = {widget.get("spec", {}).get("widgetType") for widget in investigation}

    assert {"counter", "bar", "line", "table"}.issubset(overview_types)
    assert {"counter", "bar", "table", "filter-single-select"}.issubset(investigation_types)

    detail_tables = [widget for widget in investigation if widget.get("spec", {}).get("widgetType") == "table"]
    assert len(detail_tables) >= 2
    for widget in detail_tables:
        table = widget["spec"]
        assert table["version"] == 1
        assert table["itemsPerPage"] >= 20
        assert table["paginationSize"] == "default"
        assert "invisibleColumns" in table
        assert "withRowNumber" in table
        assert "condensed" in table
        assert "allowHTMLByDefault" in table
        assert all(
            {"fieldName", "displayName", "order", "visible", "type", "displayAs"}.issubset(column)
            for column in table["encodings"]["columns"]
        )


def test_overview_pay_period_table_is_grouped_and_drillthrough_ready():
    dashboard = _built_dashboard()
    period_table = next(
        widget for widget in _widgets(_page(dashboard, "overview"))
        if widget.get("name") == "period_summary"
    )
    query = period_table["queries"][0]["query"]
    assert query["datasetName"] == "investigation"
    assert query["disaggregated"] is False
    fields = {field["name"] for field in query["fields"]}
    assert {"employee_pay_period", "employee_name", "pay_period_start", "reconciliation_status"}.issubset(fields)
    assert _page(dashboard, "investigation")["pageType"] == "PAGE_TYPE_CANVAS"


def test_investigation_view_prevents_pay_period_double_counting():
    source = (ROOT / "notebooks" / "00e_setup_investigation_view.py").read_text(encoding="utf-8")

    assert "v_audit_investigation_latest" in source
    assert "ROW_NUMBER() OVER" in source
    assert "pay_period_row_number" in source
    assert "pay_period_marker" in source
    assert "period_expected_amount_once" in source
    assert "actual_auditable_amount_once" in source
    assert "underpayment_amount_once" in source
    assert "LEFT JOIN" in source
    assert "v_reconciliation_latest" in source


def test_setup_builds_investigation_view_before_dashboard_verification():
    jobs = (ROOT / "resources" / "jobs.yml").read_text(encoding="utf-8")
    verifier = (ROOT / "notebooks" / "00d_verify_dashboard.py").read_text(encoding="utf-8")

    assert "task_key: setup_investigation_view" in jobs
    assert "../notebooks/00e_setup_investigation_view.py" in jobs
    assert "task_key: verify_dashboard" in jobs
    assert "- task_key: setup_investigation_view" in jobs
    assert "payroll_compliance.spec.json" in verifier
    assert "lakeview_builder.py" in verifier
    assert "interactive filters" in verifier.lower()
    assert "obsolete filter associativity expression" in verifier
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
