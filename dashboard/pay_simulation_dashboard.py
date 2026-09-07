from __future__ import annotations


def _f(dataset: str, field: str) -> dict:
    return {"dataset": dataset, "field": field}


def _text(name, text, position):
    return {"type": "text", "name": name, "text": text, "position": position}


def _filter(name, title, position, *, dataset, field, selection="multi"):
    return {
        "type": "filter",
        "name": name,
        "dataset": dataset,
        "field": field,
        "title": title,
        "selection": selection,
        "position": position,
    }


def _counter(name, title, expression, position, *, currency=False, decimals=0):
    result = {
        "type": "counter",
        "name": name,
        "dataset": "pay_review",
        "title": title,
        "expression": expression,
        "decimals": decimals,
        "position": position,
    }
    if currency:
        result["format"] = "currency"
    return result


def _bar(name, title, x, expression, position, *, horizontal=False, currency=False, color=None):
    result = {
        "type": "bar",
        "name": name,
        "dataset": "pay_review",
        "title": title,
        "x": x,
        "x_title": x.replace("_", " ").title(),
        "y_expression": expression,
        "y_name": "value",
        "y_title": "Value",
        "position": position,
    }
    if horizontal:
        result["orientation"] = "horizontal"
    if currency:
        result["format"] = "currency"
        result["decimals"] = 2
    if color:
        result["color"] = color
    return result


def _table(name, title, position, columns, description=None):
    result = {
        "type": "table",
        "name": name,
        "dataset": "pay_review",
        "title": title,
        "position": position,
        "columns": columns,
    }
    if description:
        result["description"] = description
    return result


def _append_filter_field(global_page: dict, widget_name: str, field: str) -> None:
    widget = next((w for w in global_page.get("widgets", []) if w.get("name") == widget_name), None)
    if widget is None:
        return
    fields = widget.setdefault("fields", [])
    candidate = _f("pay_review", field)
    if candidate not in fields:
        fields.append(candidate)


def enhance_spec(spec: dict) -> dict:
    datasets = spec.setdefault("datasets", [])
    if not any(ds.get("name") == "pay_review" for ds in datasets):
        datasets.append(
            {
                "name": "pay_review",
                "display_name": "Roster Pay Simulation and Confirmation Review",
                "query": "SELECT * FROM v_pay_review_employee_master",
            }
        )

    global_page = next((p for p in spec.get("pages", []) if p.get("page_type") == "PAGE_TYPE_GLOBAL_FILTERS"), None)
    if global_page is not None:
        _append_filter_field(global_page, "global_run", "audit_run_id")
        _append_filter_field(global_page, "global_date", "audit_window_start")
        _append_filter_field(global_page, "global_employee", "employee_name")
        _append_filter_field(global_page, "global_stream", "classification_family")
        _append_filter_field(global_page, "global_level", "scenario_level")
        _append_filter_field(global_page, "global_paypoint", "scenario_pay_point")
        _append_filter_field(global_page, "global_emp_type", "scenario_employment_type")
        if not any(w.get("name") == "global_pay_review_status" for w in global_page.get("widgets", [])):
            global_page["widgets"].append(
                _filter(
                    "global_pay_review_status",
                    "Roster Pay Review Status",
                    [0, 3, 3, 1],
                    dataset="pay_review",
                    field="status_display",
                )
            )

    overview = next((p for p in spec.get("pages", []) if p.get("name") == "audit_overview"), None)
    if overview is not None and not any(w.get("name") == "pay_review_title" for w in overview.get("widgets", [])):
        overview["widgets"].extend(
            [
                _text(
                    "pay_review_title",
                    "### Roster Pay Simulation & Confirmation\nRoster-only audits remain useful before payroll arrives. Red means the hourly/base rate is missing or the saved scenario indicates potential underpayment; orange means further Award evidence is required; green means the saved-rate simulation meets the numeric minimum but is still not proof of actual payroll payment.",
                    [0, 27, 6, 2],
                ),
                _counter(
                    "pay_missing_confirmations",
                    "Missing Rate Confirmations",
                    "SUM(CASE WHEN `review_status`='MISSING_PAY_RATE_CONFIRMATION' THEN 1 ELSE 0 END)",
                    [0, 29, 1, 2],
                ),
                _counter(
                    "pay_confirmed",
                    "Rates Confirmed",
                    "SUM(CASE WHEN `confirmation_id` IS NOT NULL THEN 1 ELSE 0 END)",
                    [1, 29, 1, 2],
                ),
                _counter(
                    "pay_potential_under",
                    "Potential Underpayment",
                    "SUM(CASE WHEN `review_status` IN ('POTENTIAL_BASE_RATE_UNDERPAYMENT','POTENTIAL_UNDERPAYMENT') THEN 1 ELSE 0 END)",
                    [2, 29, 1, 2],
                ),
                _counter(
                    "pay_award_review",
                    "Award Review Required",
                    "SUM(CASE WHEN `review_status`='RATE_CONFIRMED_REQUIRES_AWARD_REVIEW' THEN 1 ELSE 0 END)",
                    [3, 29, 1, 2],
                ),
                _counter(
                    "pay_confirmed_simulated",
                    "Confirmed-Rate Simulated Pay",
                    "SUM(COALESCE(`confirmed_rate_simulated_pay`,0))",
                    [4, 29, 1, 2],
                    currency=True,
                    decimals=2,
                ),
                _counter(
                    "pay_confirmed_variance",
                    "Confirmed-Rate Variance",
                    "SUM(COALESCE(`confirmed_rate_variance`,0))",
                    [5, 29, 1, 2],
                    currency=True,
                    decimals=2,
                ),
                _bar(
                    "pay_review_status_chart",
                    "Employee / Year Roster Pay Review Status",
                    "status_display",
                    "COUNT(`employee_id`)",
                    [0, 31, 3, 7],
                    horizontal=True,
                    color="status_display",
                ),
                _bar(
                    "pay_review_rate_employee",
                    "Confirmed Hourly Rate by Employee",
                    "employee_name",
                    "MAX(COALESCE(`confirmed_hourly_rate`,0))",
                    [3, 31, 3, 7],
                    horizontal=True,
                    currency=True,
                ),
                _table(
                    "pay_review_attention",
                    "Roster Pay Review Master",
                    [0, 38, 6, 11],
                    [
                        {"field": "status_display", "title": "Status"},
                        {"field": "employee_name", "title": "Employee"},
                        {"field": "calendar_year", "title": "Year", "kind": "integer"},
                        {"field": "confirmed_hourly_rate", "title": "Confirmed Rate", "kind": "number", "number_format": "$0.00"},
                        {"field": "confirmed_pay_model", "title": "Pay Model"},
                        {"field": "scenario_classification_name", "title": "Selected Classification"},
                        {"field": "scenario_employment_type", "title": "Employment Type"},
                        {"field": "award_base_rate_low", "title": "Award Base Low", "kind": "number", "number_format": "$0.00"},
                        {"field": "award_base_rate_high", "title": "Award Base High", "kind": "number", "number_format": "$0.00"},
                        {"field": "minimum_entitlement_low", "title": "Scenario Entitlement Low", "kind": "number", "number_format": "$0,0.00"},
                        {"field": "minimum_entitlement_high", "title": "Scenario Entitlement High", "kind": "number", "number_format": "$0,0.00"},
                        {"field": "confirmed_rate_simulated_pay", "title": "Confirmed-Rate Simulated Pay", "kind": "number", "number_format": "$0,0.00"},
                        {"field": "confirmed_rate_variance", "title": "Variance", "kind": "number", "number_format": "$0,0.00"},
                        {"field": "recommendation", "title": "Recommendation"},
                    ],
                    description="The dashboard is the roster-pay analysis surface. Use 'AuditHero - Confirm Employee Pay Rate' only when you want to persist reviewed rate evidence.",
                ),
            ]
        )

    employee_page = next((p for p in spec.get("pages", []) if p.get("name") == "employee_deep_dive"), None)
    if employee_page is not None and not any(w.get("name") == "emp_pay_review_title" for w in employee_page.get("widgets", [])):
        employee_page["widgets"].extend(
            [
                _text(
                    "emp_pay_review_title",
                    "### Roster Pay Simulation / Saved Rate Evidence\nThis section reflects the latest saved employee/year rate evidence and selected SCHADS scenario. Use 'AuditHero - Confirm Employee Pay Rate' when a reviewed rate needs to be persisted; no separate Databricks App is required.",
                    [0, 30, 6, 2],
                ),
                _filter("emp_pay_review_year", "Pay Review Year", [0, 32, 2, 1], dataset="pay_review", field="calendar_year", selection="single"),
                _filter("emp_pay_review_status_filter", "Review Status", [2, 32, 2, 1], dataset="pay_review", field="status_display"),
                _counter("emp_confirmed_rate", "Confirmed Hourly Rate", "MAX(COALESCE(`confirmed_hourly_rate`,0))", [0, 33, 1, 2], currency=True, decimals=2),
                _counter("emp_selected_minimum", "Selected Scenario Minimum", "MAX(COALESCE(`selected_award_minimum_entitlement`,0))", [1, 33, 1, 2], currency=True, decimals=2),
                _counter("emp_simulated_pay", "Confirmed-Rate Simulated Pay", "MAX(COALESCE(`confirmed_rate_simulated_pay`,0))", [2, 33, 1, 2], currency=True, decimals=2),
                _counter("emp_simulated_variance", "Simulation Variance", "MAX(COALESCE(`confirmed_rate_variance`,0))", [3, 33, 1, 2], currency=True, decimals=2),
                _counter("emp_scenario_low", "Scenario Range Low", "MIN(COALESCE(`minimum_entitlement_low`,0))", [4, 33, 1, 2], currency=True, decimals=2),
                _counter("emp_scenario_high", "Scenario Range High", "MAX(COALESCE(`minimum_entitlement_high`,0))", [5, 33, 1, 2], currency=True, decimals=2),
                _table(
                    "emp_pay_review_detail",
                    "Employee Roster Pay Review",
                    [0, 35, 6, 9],
                    [
                        {"field": "status_display", "title": "Status"},
                        {"field": "calendar_year", "title": "Year", "kind": "integer"},
                        {"field": "confirmed_hourly_rate", "title": "Confirmed Rate", "kind": "number", "number_format": "$0.00"},
                        {"field": "confirmed_pay_model", "title": "Pay Model"},
                        {"field": "scenario_classification_name", "title": "Selected Classification"},
                        {"field": "scenario_level", "title": "Level", "kind": "integer"},
                        {"field": "scenario_pay_point", "title": "Pay Point", "kind": "integer"},
                        {"field": "scenario_employment_type", "title": "Employment Type"},
                        {"field": "selected_award_minimum_base_rate", "title": "Award Base", "kind": "number", "number_format": "$0.00"},
                        {"field": "selected_award_minimum_entitlement", "title": "Award Minimum", "kind": "number", "number_format": "$0,0.00"},
                        {"field": "confirmed_rate_simulated_pay", "title": "Simulated Pay", "kind": "number", "number_format": "$0,0.00"},
                        {"field": "confirmed_rate_variance", "title": "Variance", "kind": "number", "number_format": "$0,0.00"},
                        {"field": "confirmation_source_type", "title": "Evidence Source"},
                        {"field": "confirmation_source_reference", "title": "Reference"},
                        {"field": "confirmed_by", "title": "Confirmed By"},
                        {"field": "confirmed_at", "title": "Confirmed At"},
                        {"field": "recommendation", "title": "Recommendation"},
                    ],
                ),
            ]
        )

    return spec
