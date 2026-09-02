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

    for page_name in ("global_filters", "overview", "investigation"):
        for widget in _widgets(_page(dashboard, page_name)):
            for query in widget.get("queries", []):
                assert query["query"]["datasetName"] == "investigation"


def test_dashboard_has_global_and_page_level_field_filters():
    dashboard = _built_dashboard()
    global_page = _page(dashboard, "global_filters")
    investigation = _widgets(_page(dashboard, "investigation"))

    assert global_page["pageType"] == "PAGE_TYPE_GLOBAL_FILTERS"
    global_filters = [
        widget for widget in _widgets(global_page)
        if str(widget.get("spec", {}).get("widgetType", "")).startswith("filter-")
    ]
    local_filters = [
        widget for widget in investigation
        if str(widget.get("spec", {}).get("widgetType", "")).startswith("filter-")
    ]
    assert global_filters
    assert local_filters

    fields = {
        widget["spec"]["encodings"]["fields"][0]["fieldName"]
        for widget in [*global_filters, *local_filters]
    }
    assert {
        "pay_period_start",
        "reconciliation_status",
        "employee_name",
        "employment_type",
        "classification_code",
        "work_group",
        "state",
        "employee_pay_period",
    }.issubset(fields)
    assert any(widget["spec"]["widgetType"] == "filter-date-range-picker" for widget in global_filters)
    assert any(widget["spec"]["widgetType"] == "filter-single-select" for widget in local_filters)

    for widget in [*global_filters, *local_filters]:
        assert widget["spec"]["version"] == 2
        assert widget["spec"]["frame"]["showTitle"] is True
        assert "associative_filter_predicate_group" not in json.dumps(widget)
        for query in widget["queries"]:
            assert query["query"]["disaggregated"] is False
            assert len(query["query"]["fields"]) == 1


def test_dashboard_contains_kpis_charts_and_current_table_specs():
    dashboard = _built_dashboard()
    overview = _widgets(_page(dashboard, "overview"))
    investigation = _widgets(_page(dashboard, "investigation"))

    overview_types = {widget.get("spec", {}).get("widgetType") for widget in overview}
    investigation_types = {widget.get("spec", {}).get("widgetType") for widget in investigation}

    assert {"counter", "bar", "line", "table"}.issubset(overview_types)
    assert {"counter", "bar", "table", "filter-single-select"}.issubset(investigation_types)

    all_tables = [
        widget for page in dashboard["pages"] for widget in _widgets(page)
        if widget.get("spec", {}).get("widgetType") == "table"
    ]
    assert len(all_tables) >= 5
    for widget in all_tables:
        table = widget["spec"]
        assert table["version"] == 2
        assert all(
            {"fieldName", "displayName"}.issubset(column)
            for column in table["encodings"]["columns"]
        )

    evidence = next(widget for widget in investigation if widget.get("name") == "calculation_evidence")
    evidence_columns = {column["fieldName"]: column for column in evidence["spec"]["encodings"]["columns"]}
    assert evidence_columns["calculation_evidence"]["displayAs"] == "json"


def test_text_and_time_series_widgets_use_current_schema():
    dashboard = _built_dashboard()
    overview = _widgets(_page(dashboard, "overview"))

    title = next(widget for widget in overview if widget.get("name") == "overview_title")
    assert "multilineTextboxSpec" in title
    assert "textbox_spec" not in title

    variance = next(widget for widget in overview if widget.get("name") == "variance_trend")
    assert variance["spec"]["version"] == 3
    assert variance["spec"]["encodings"]["x"]["scale"]["type"] == "temporal"


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
    assert "Drill to" in period_table["spec"]["frame"]["description"]
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
