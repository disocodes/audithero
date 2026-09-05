from __future__ import annotations

from copy import deepcopy


def _f(dataset: str, field: str) -> dict:
    return {"dataset": dataset, "field": field}


def _filter(name, title, position, *, dataset=None, field=None, fields=None, selection="multi", filter_type=None, description=None):
    result = {"type": "filter", "name": name, "title": title, "position": position, "selection": selection}
    if fields is not None:
        result["fields"] = fields
    else:
        result["dataset"] = dataset
        result["field"] = field
    if filter_type:
        result["filter_type"] = filter_type
    if description:
        result["description"] = description
    return result


def _text(name, text, position):
    return {"type": "text", "name": name, "text": text, "position": position}


def _counter(name, dataset, title, expression, position, *, currency=False, decimals=0, description=None):
    result = {
        "type": "counter", "name": name, "dataset": dataset, "title": title,
        "expression": expression, "decimals": decimals, "position": position,
    }
    if currency:
        result["format"] = "currency"
    if description:
        result["description"] = description
    return result


def _bar(name, dataset, title, x, y_expression, position, *, y_name="value", x_title=None, y_title=None, currency=False, horizontal=False, color=None):
    result = {
        "type": "bar", "name": name, "dataset": dataset, "title": title,
        "x": x, "x_title": x_title or x, "y_expression": y_expression,
        "y_name": y_name, "y_title": y_title or y_name, "position": position,
    }
    if currency:
        result["format"] = "currency"
        result["decimals"] = 2
    if horizontal:
        result["orientation"] = "horizontal"
    if color:
        result["color"] = color
    return result


def _line(name, dataset, title, x, y_expression, position, *, y_name="value", x_title=None, y_title=None, currency=False):
    result = {
        "type": "line", "name": name, "dataset": dataset, "title": title,
        "x": x, "x_title": x_title or x, "x_scale": "temporal",
        "y_expression": y_expression, "y_name": y_name, "y_title": y_title or y_name,
        "position": position,
    }
    if currency:
        result["format"] = "currency"
        result["decimals"] = 2
    return result


def _table(name, dataset, title, position, columns, *, description=None):
    result = {"type": "table", "name": name, "dataset": dataset, "title": title, "position": position, "columns": columns}
    if description:
        result["description"] = description
    return result


def _global_filters():
    criteria_sets = ["criteria", "penalties", "overtime", "meal_breaks", "sleep_broken", "evidence"]
    scenario_sets = ["scenario", *criteria_sets, "scenario_rest"]
    employee_sets = ["investigation", "scenario", *criteria_sets, "scenario_rest", "reconciliation"]
    run_sets = ["investigation", "scenario", *criteria_sets, "scenario_rest", "reconciliation", "runs"]

    return [
        _filter(
            "global_run", "Audit Run", [0, 0, 2, 1],
            fields=[_f(dataset, "audit_run_id") for dataset in run_sets], selection="single",
            description="Filters persisted run-scoped audit datasets. Rule coverage and readiness history are intentionally independent.",
        ),
        _filter(
            "global_date", "Audit / Shift Date", [2, 0, 2, 1],
            fields=[
                _f("investigation", "shift_start"), _f("scenario", "shift_start"),
                *[_f(dataset, "shift_start") for dataset in criteria_sets],
                _f("scenario_rest", "next_shift_start"), _f("reconciliation", "pay_period_start"),
                _f("runs", "audit_window_start"),
            ],
            filter_type="date-range",
            description="Uses the equivalent date field in each audit dataset so the selected range follows you across pages.",
        ),
        _filter("global_employee", "Employee", [4, 0, 2, 1], fields=[_f(dataset, "employee_name") for dataset in employee_sets]),
        _filter("global_stream", "SCHADS Stream", [0, 1, 2, 1], fields=[_f(dataset, "classification_family") for dataset in scenario_sets]),
        _filter("global_level", "Level", [2, 1, 1, 1], fields=[_f(dataset, "scenario_level") for dataset in scenario_sets]),
        _filter("global_paypoint", "Pay Point", [3, 1, 1, 1], fields=[_f(dataset, "scenario_pay_point") for dataset in scenario_sets]),
        _filter("global_emp_type", "Scenario Employment Type", [4, 1, 2, 1], fields=[_f(dataset, "scenario_employment_type") for dataset in scenario_sets]),
        _filter("global_scenario_status", "Scenario Status", [0, 2, 2, 1], dataset="scenario", field="scenario_status"),
        _filter("global_rate_status", "Base Rate Status", [2, 2, 2, 1], dataset="scenario", field="base_rate_status"),
        _filter(
            "global_definitive_status", "Definitive Pay Status", [4, 2, 2, 1],
            fields=[_f("reconciliation", "status"), _f("investigation", "reconciliation_status")],
        ),
    ]


def _overview_page():
    return {
        "name": "audit_overview", "display_name": "Audit Overview", "widgets": [
            _text(
                "overview_title",
                "## Audit Overview\nStart here. This page separates the definitive payroll result from scenario exploration and surfaces evidence that still requires attention. Global filters are linked across the underlying audit datasets.",
                [0, 0, 6, 2],
            ),
            _counter("ov_employees", "investigation", "Employees in Scope", "COUNT(DISTINCT `employee_id`)", [0, 2, 1, 2]),
            _counter("ov_shifts", "investigation", "Definitive Shifts", "COUNT(DISTINCT `timesheet_id`)", [1, 2, 1, 2]),
            _counter("ov_review_shifts", "investigation", "Shifts Requiring Review", "SUM(COALESCE(`review_shift_marker`,0))", [2, 2, 1, 2]),
            _counter("ov_expected", "reconciliation", "Expected Pay", "SUM(COALESCE(`expected_amount`,0))", [3, 2, 1, 2], currency=True, decimals=2),
            _counter("ov_actual", "reconciliation", "Actual Auditable Pay", "SUM(COALESCE(`actual_auditable_amount`,0))", [4, 2, 1, 2], currency=True, decimals=2),
            _counter(
                "ov_shortfall", "reconciliation", "Potential Underpayment",
                "SUM(CASE WHEN `status`='UNDERPAID' THEN GREATEST(-COALESCE(`variance_actual_minus_expected`,0),0) ELSE 0 END)",
                [5, 2, 1, 2], currency=True, decimals=2,
            ),
            _bar("ov_status", "reconciliation", "Definitive Pay Period Status", "status", "COUNT(`employee_id`)", [0, 4, 3, 6], y_name="periods", y_title="Pay Periods", color="status"),
            _bar(
                "ov_under_by_employee", "investigation", "Potential Underpayment by Employee", "employee_name",
                "SUM(COALESCE(`underpayment_amount_once`,0))", [3, 4, 3, 6], y_name="underpayment",
                y_title="Potential Underpayment", currency=True, horizontal=True,
            ),
            _bar(
                "ov_evidence_area", "evidence", "Evidence / Review Findings by Audit Area", "criterion_group",
                "COUNT(`criterion`)", [0, 10, 3, 7], y_name="findings", y_title="Findings", horizontal=True,
            ),
            _bar(
                "ov_rate_findings", "scenario", "Below-Minimum Rate Findings by Employee", "employee_name",
                "SUM(CASE WHEN `base_rate_status`='BELOW_MINIMUM' THEN 1 ELSE 0 END)", [3, 10, 3, 7],
                y_name="below_minimum", y_title="Below-Minimum Shifts", horizontal=True,
            ),
            _table(
                "ov_attention", "investigation", "Definitive Shift Attention List", [0, 17, 6, 10],
                [
                    {"field": "employee_name", "title": "Employee"}, {"field": "shift_start", "title": "Shift Start"},
                    {"field": "worked_hours", "title": "Hours", "kind": "number"}, {"field": "classification_code", "title": "Classification"},
                    {"field": "employment_type", "title": "Employment Type"},
                    {"field": "shift_expected_amount", "title": "Expected", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "entitlement_status", "title": "Shift Status"}, {"field": "reconciliation_status", "title": "Pay Period Status"},
                    {"field": "review_flags", "title": "Review Flags"},
                ],
                description="Use Employee Deep Dive or Definitive Shift Investigation for the complete evidence chain.",
            ),
        ],
    }


def _employee_page():
    return {
        "name": "employee_deep_dive", "display_name": "Employee Deep Dive", "widgets": [
            _text(
                "employee_title",
                "## Employee Deep Dive\nUse the global Employee filter, then optionally choose one employee/pay-period below. This ties definitive shifts, reconciliation and scenario sensitivity together.",
                [0, 0, 6, 2],
            ),
            _filter("employee_period", "Employee + Pay Period", [0, 2, 3, 1], dataset="investigation", field="employee_pay_period", selection="single"),
            _filter("employee_shift_status", "Shift Status", [3, 2, 1, 1], dataset="investigation", field="entitlement_status"),
            _filter("employee_recon_status", "Pay Status", [4, 2, 2, 1], dataset="investigation", field="reconciliation_status"),
            _counter("emp_shifts", "investigation", "Shifts", "COUNT(DISTINCT `timesheet_id`)", [0, 3, 1, 2]),
            _counter("emp_hours", "investigation", "Worked Hours", "SUM(COALESCE(`worked_hours`,0))", [1, 3, 1, 2], decimals=2),
            _counter("emp_expected", "investigation", "Expected Pay", "SUM(COALESCE(`period_expected_amount_once`,0))", [2, 3, 1, 2], currency=True, decimals=2),
            _counter("emp_actual", "investigation", "Actual Auditable", "SUM(COALESCE(`actual_auditable_amount_once`,0))", [3, 3, 1, 2], currency=True, decimals=2),
            _counter("emp_under", "investigation", "Underpayment", "SUM(COALESCE(`underpayment_amount_once`,0))", [4, 3, 1, 2], currency=True, decimals=2),
            _counter("emp_review", "investigation", "Review Shifts", "SUM(COALESCE(`review_shift_marker`,0))", [5, 3, 1, 2]),
            _line("emp_shift_expected", "investigation", "Expected Entitlement by Shift Date", "shift_start", "SUM(COALESCE(`shift_expected_amount`,0))", [0, 5, 3, 6], y_name="expected", y_title="Expected Pay", currency=True),
            _bar("emp_scenario_level", "scenario", "Scenario Expected Pay by Level", "scenario_level", "SUM(COALESCE(`expected_amount`,0))", [3, 5, 3, 6], y_name="expected", y_title="Scenario Expected Pay", currency=True),
            _table(
                "emp_shift_table", "investigation", "Employee Definitive Shift Detail", [0, 11, 6, 11],
                [
                    {"field": "timesheet_id", "title": "Timesheet ID"}, {"field": "shift_start", "title": "Shift Start"},
                    {"field": "shift_end", "title": "Shift End"}, {"field": "worked_hours", "title": "Hours", "kind": "number"},
                    {"field": "employment_type", "title": "Employment Type"}, {"field": "classification_code", "title": "Classification"},
                    {"field": "base_hourly_rate", "title": "Award Rate", "kind": "number", "number_format": "$0.00"},
                    {"field": "shift_expected_amount", "title": "Expected", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "entitlement_status", "title": "Shift Status"}, {"field": "review_flags", "title": "Review Flags"},
                ],
            ),
            _table(
                "emp_recon_table", "reconciliation", "Employee Pay-Period Reconciliation", [0, 22, 6, 8],
                [
                    {"field": "employee_name", "title": "Employee"}, {"field": "pay_period_start", "title": "Period Start"},
                    {"field": "pay_period_end", "title": "Period End"},
                    {"field": "expected_amount", "title": "Expected", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "actual_auditable_amount", "title": "Actual", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "variance_actual_minus_expected", "title": "Variance", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "status", "title": "Status"},
                ],
            ),
        ],
    }


def _components_page():
    return {
        "name": "audit_components", "display_name": "Audit Components", "widgets": [
            _text(
                "components_title",
                "## Audit Components\nA consolidated view of every SCHADS criterion produced for the selected scenario. Use it to understand which Award areas contribute hours, amounts or evidence-review findings.",
                [0, 0, 6, 2],
            ),
            _filter("comp_group", "Audit Area", [0, 2, 2, 1], dataset="criteria", field="criterion_group"),
            _filter("comp_criterion", "Criterion / Component", [2, 2, 2, 1], dataset="criteria", field="criterion"),
            _filter("comp_day", "Day Type", [4, 2, 1, 1], dataset="criteria", field="day_type"),
            _filter("comp_shift", "Shift Type", [5, 2, 1, 1], dataset="criteria", field="shift_type"),
            _counter("comp_count", "criteria", "Criterion Rows", "COUNT(`criterion`)", [0, 3, 1, 2]),
            _counter("comp_hours", "criteria", "Component Hours", "SUM(COALESCE(`hours`,0))", [1, 3, 1, 2], decimals=2),
            _counter("comp_amount", "criteria", "Calculated Component Amount", "SUM(COALESCE(`criterion_amount`,0))", [2, 3, 2, 2], currency=True, decimals=2),
            _counter("comp_review", "criteria", "Review Criteria", "SUM(CASE WHEN `criterion`='EVIDENCE_OR_RULE_REVIEW' THEN 1 ELSE 0 END)", [4, 3, 1, 2]),
            _counter("comp_clauses", "criteria", "Award Clauses Referenced", "COUNT(DISTINCT `clause`)", [5, 3, 1, 2]),
            _bar("comp_amount_area", "criteria", "Calculated Amount by Audit Area", "criterion_group", "SUM(COALESCE(`criterion_amount`,0))", [0, 5, 3, 7], y_name="amount", y_title="Calculated Amount", currency=True, horizontal=True),
            _bar("comp_count_area", "criteria", "Criteria Count by Audit Area", "criterion_group", "COUNT(`criterion`)", [3, 5, 3, 7], y_name="criteria", y_title="Criteria", horizontal=True),
            _table(
                "comp_detail", "criteria", "All Scenario Criteria Detail", [0, 12, 6, 12],
                [
                    {"field": "employee_name", "title": "Employee"}, {"field": "shift_start", "title": "Shift Start"},
                    {"field": "scenario_classification_code", "title": "Classification"}, {"field": "scenario_employment_type", "title": "Employment Type"},
                    {"field": "criterion_group", "title": "Audit Area"}, {"field": "criterion", "title": "Criterion"},
                    {"field": "hours", "title": "Hours", "kind": "number"}, {"field": "multiplier", "title": "Multiplier", "kind": "number"},
                    {"field": "effective_hourly_rate", "title": "Rate", "kind": "number", "number_format": "$0.00"},
                    {"field": "criterion_amount", "title": "Amount", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "day_type", "title": "Day Type"}, {"field": "shift_type", "title": "Shift Type"},
                    {"field": "clause", "title": "Clause"}, {"field": "detail", "title": "Calculation Evidence", "kind": "json"},
                ],
            ),
        ],
    }


def _data_quality_page():
    return {
        "name": "data_quality", "display_name": "Audit Runs & Data Quality", "widgets": [
            _text(
                "dq_title",
                "## Audit Runs and Data Quality\nConfirm what period was run, whether actual-pay evidence was available, and which source/readiness controls still require attention.",
                [0, 0, 6, 2],
            ),
            _filter("dq_run_type", "Run Type", [0, 2, 2, 1], dataset="runs", field="run_type"),
            _filter("dq_run_status", "Run Status", [2, 2, 2, 1], dataset="runs", field="status"),
            _filter("dq_readiness_status", "Readiness Status", [4, 2, 2, 1], dataset="readiness", field="status"),
            _table(
                "dq_runs", "runs", "Audit Run History", [0, 3, 6, 10],
                [
                    {"field": "audit_run_id", "title": "Audit Run ID"}, {"field": "finished_at", "title": "Finished"},
                    {"field": "run_type", "title": "Run Type"}, {"field": "audit_window_start", "title": "Start"},
                    {"field": "audit_window_end", "title": "End"}, {"field": "status", "title": "Status"},
                    {"field": "actual_pay_source", "title": "Actual Pay Source"}, {"field": "employees", "title": "Employees", "kind": "integer"},
                    {"field": "timesheets", "title": "Timesheets", "kind": "integer"}, {"field": "underpaid_periods", "title": "Underpaid", "kind": "integer"},
                    {"field": "overpaid_periods", "title": "Overpaid", "kind": "integer"}, {"field": "review_periods", "title": "Review", "kind": "integer"},
                    {"field": "message", "title": "Run Detail"},
                ],
            ),
            _bar("dq_findings_type", "readiness", "Readiness Findings by Type", "finding_type", "COUNT(`finding_type`)", [0, 13, 3, 7], y_name="findings", y_title="Findings", horizontal=True),
            _bar("dq_findings_status", "readiness", "Readiness Findings by Status", "status", "COUNT(`status`)", [3, 13, 3, 7], y_name="findings", y_title="Findings", color="status"),
            _table(
                "dq_readiness", "readiness", "Source and Readiness Findings", [0, 20, 6, 10],
                [
                    {"field": "finding_type", "title": "Finding Type"}, {"field": "source_key", "title": "Source"},
                    {"field": "status", "title": "Status"}, {"field": "detail", "title": "Detail"},
                    {"field": "checked_at", "title": "Checked At"},
                ],
            ),
        ],
    }


def enhance_spec(base_spec: dict) -> dict:
    spec = deepcopy(base_spec)

    global_page = next((page for page in spec.get("pages", []) if page.get("page_type") == "PAGE_TYPE_GLOBAL_FILTERS"), None)
    if global_page is None:
        global_page = {"name": "global_filters", "display_name": "Audit Filters", "page_type": "PAGE_TYPE_GLOBAL_FILTERS", "widgets": []}
        spec.setdefault("pages", []).insert(0, global_page)
    global_page["display_name"] = "Audit Filters"
    global_page["widgets"] = _global_filters()

    additions = {
        "audit_overview": _overview_page(),
        "employee_deep_dive": _employee_page(),
        "audit_components": _components_page(),
        "data_quality": _data_quality_page(),
    }
    existing_names = {page.get("name") for page in spec.get("pages", [])}
    insert_at = spec["pages"].index(global_page) + 1
    for name in ("audit_overview", "employee_deep_dive", "audit_components"):
        if name not in existing_names:
            spec["pages"].insert(insert_at, additions[name])
            insert_at += 1
    if "data_quality" not in existing_names:
        controls_index = next((i for i, page in enumerate(spec["pages"]) if page.get("name") == "controls_rules"), len(spec["pages"]))
        spec["pages"].insert(controls_index, additions["data_quality"])

    if len(spec["pages"]) > 15:
        raise ValueError(f"AuditHero dashboard exceeds the Databricks 15-page limit: {len(spec['pages'])}")

    spec["uiSettings"] = {
        "theme": {
            "canvasBackgroundColor": {"light": "#F7F9FC", "dark": "#161B22"},
            "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#0D1117"},
            "fontColor": {"light": "#17202A", "dark": "#E6EDF3"},
            "selectionColor": {"light": "#0B6E99", "dark": "#58A6C9"},
            "visualizationColors": ["#0B6E99", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51", "#6C63A8", "#4C78A8"],
            "widgetHeaderAlignment": "LEFT",
            "widgetCornerRadius": 8,
        }
    }
    return spec
