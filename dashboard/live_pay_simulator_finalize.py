from __future__ import annotations

import importlib.util
from pathlib import Path


def _default_values(data_type: str, value: str) -> dict:
    return {
        "values": {
            "dataType": data_type,
            "values": [{"value": value}],
        }
    }


def _ensure_parameter(ds: dict, keyword: str, display_name: str, data_type: str, default_value: str) -> None:
    parameters = ds.setdefault("parameters", [])
    parameter = next((p for p in parameters if p.get("keyword") == keyword), None)
    if parameter is None:
        parameter = {"keyword": keyword, "dataType": data_type}
        parameters.append(parameter)
    parameter["displayName"] = display_name
    parameter["dataType"] = data_type
    parameter["defaultSelection"] = _default_values(data_type, default_value)


def _apply_current_layout(spec: dict) -> dict:
    """Apply the shared 12-column layout finalizer from this dashboard directory."""
    layout_file = Path(__file__).with_name("dashboard_layout_finalize.py")
    if not layout_file.exists():
        raise FileNotFoundError(f"AuditHero dashboard layout finalizer not found: {layout_file}")
    module_spec = importlib.util.spec_from_file_location("audithero_dashboard_layout_finalize", layout_file)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"AuditHero dashboard layout finalizer could not be loaded: {layout_file}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.enhance_spec(spec)


def _assert_live_simulator(spec: dict) -> None:
    required = {
        "live_sim_title",
        "sim_year",
        "sim_scenario",
        "sim_exact_rate",
        "sim_pay_model",
        "sim_selected_rate_kpi",
        "sim_simulated_pay",
        "sim_variance",
        "sim_shift_table",
        "sim_component_table",
    }
    present = {
        widget.get("name")
        for page in spec.get("pages", []) or []
        for widget in page.get("widgets", []) or []
    }
    missing = sorted(required - present)
    if missing:
        raise ValueError(
            "AuditHero live simulator enhancement is incomplete; missing dashboard widgets: "
            + ", ".join(missing)
        )

    employee_page = next(
        (page for page in spec.get("pages", []) if page.get("name") == "employee_deep_dive"),
        None,
    )
    if employee_page is None:
        raise ValueError("AuditHero live simulator requires the Employee Deep Dive page")

    simulator_positions = [
        widget.get("position")
        for widget in employee_page.get("widgets", []) or []
        if widget.get("name") in required
    ]
    if not simulator_positions:
        raise ValueError("AuditHero live simulator has no positioned widgets")


def _is_simulator_widget(widget: dict) -> bool:
    name = str(widget.get("name", ""))
    return name.startswith("sim_") or name.startswith("live_sim")


def _shift_simulator_from(page: dict, start_y: int, delta: int) -> None:
    for widget in page.get("widgets", []) or []:
        if not _is_simulator_widget(widget):
            continue
        position = widget.get("position")
        if not isinstance(position, list) or len(position) != 4:
            continue
        if position[1] >= start_y:
            position = list(position)
            position[1] += delta
            widget["position"] = position


def _insert_simulator_heading(page: dict, name: str, title: str, detail: str, y: int) -> None:
    if any(widget.get("name") == name for widget in page.get("widgets", []) or []):
        return
    _shift_simulator_from(page, y, 2)
    page.setdefault("widgets", []).append(
        {
            "type": "text",
            "name": name,
            "text": f"### {title}\n{detail}",
            "position": [0, y, 6, 2],
        }
    )


def _apply_simulator_language_and_sections(page: dict) -> None:
    """Make the simulator read as a calculation workspace, not a KPI tracker."""
    title = next((w for w in page.get("widgets", []) if w.get("name") == "live_sim_title"), None)
    if title:
        title["text"] = (
            "## Roster Pay Simulator\n"
            "### Simulation Controls\n"
            "Choose an employee, year and SCHADS scenario, then type/search an exact hourly rate and choose how that rate should be interpreted. "
            "**Every calculation and detail below uses the same connected simulation state.** "
            "These values are what-if calculations from roster evidence and are not actual-pay evidence until separately confirmed."
        )

    # Insert headings from the bottom upward so each insertion can shift the later
    # simulator block without disturbing the relative arrangement of earlier rows.
    _insert_simulator_heading(
        page,
        "sim_award_components_heading",
        "Award Components",
        "Inspect overtime, penalties, breaks, allowances and other SCHADS calculation components behind the selected scenario.",
        81,
    )
    _insert_simulator_heading(
        page,
        "sim_shift_calculations_heading",
        "Shift Calculations",
        "Review how the selected rate changes the calculated outcome for each rostered shift.",
        72,
    )
    _insert_simulator_heading(
        page,
        "sim_pay_outcomes_heading",
        "Break-even & Pay Outcomes",
        "Compare the selected rate with SCHADS minimums, break-even rates, calculated pay and variance.",
        51,
    )
    _insert_simulator_heading(
        page,
        "sim_summary_heading",
        "Simulation Summary",
        "Calculated values for the currently selected employee, year, scenario, hourly rate and pay interpretation.",
        49,
    )

    # These are calculation-summary tiles. Their internal widget identifiers are
    # intentionally left stable because they are deployment assertions, not labels
    # shown to dashboard users.
    selected_rate = next((w for w in page.get("widgets", []) if w.get("name") == "sim_selected_rate_kpi"), None)
    if selected_rate:
        selected_rate["title"] = "Selected Hourly Rate"

    simulated_pay = next((w for w in page.get("widgets", []) if w.get("name") == "sim_simulated_pay"), None)
    if simulated_pay:
        simulated_pay["title"] = "Calculated Pay at Selected Rate"

    variance = next((w for w in page.get("widgets", []) if w.get("name") == "sim_variance"), None)
    if variance:
        variance["title"] = "Calculated Variance"


def enhance_spec(spec: dict) -> dict:
    datasets = {ds.get("name"): ds for ds in spec.get("datasets", [])}

    for name in ("pay_sim_live", "pay_sim_shift_live"):
        ds = datasets.get(name)
        if not ds:
            continue
        _ensure_parameter(ds, "assumed_rate", "Assumed hourly rate", "DECIMAL", "50.00")
        _ensure_parameter(ds, "pay_model", "Pay interpretation", "STRING", "BASE_PLUS_SCHADS_MULTIPLIERS")

    for name in ("pay_sim_components_live", "pay_rate_position"):
        ds = datasets.get(name)
        if ds:
            _ensure_parameter(ds, "assumed_rate", "Assumed hourly rate", "DECIMAL", "50.00")

    # Components use the pay-model parameter differently from the employee/shift
    # summary. Under a flat/loaded model the selected hourly amount is treated as
    # aggregate coverage and must not be used to re-base individual Award penalty
    # or overtime requirements. Under the base+SCHADS model rate-sensitive Award
    # components are scaled from the calculated SCHADS base.
    components = datasets.get("pay_sim_components_live")
    if components:
        _ensure_parameter(
            components,
            "pay_model",
            "Pay interpretation",
            "STRING",
            "BASE_PLUS_SCHADS_MULTIPLIERS",
        )
        query = components.get("query", "")
        marker = "c.employee_name,\n      c.shift_start,"
        if marker in query and "YEAR(c.shift_start) AS calendar_year" not in query:
            query = query.replace(
                marker,
                "c.employee_name,\n      YEAR(c.shift_start) AS calendar_year,\n      c.shift_start,",
            )

        scale_marker = (
            "WHEN s.base_hourly_rate > 0\n"
            "          THEN c.criterion_amount * (CAST(:assumed_rate AS DOUBLE) / s.base_hourly_rate)"
        )
        if scale_marker in query and "CAST(:pay_model AS STRING) = 'FLAT_LOADED_HOURLY'" not in query:
            query = query.replace(
                scale_marker,
                "WHEN CAST(:pay_model AS STRING) = 'FLAT_LOADED_HOURLY' THEN c.criterion_amount\n"
                "        WHEN s.base_hourly_rate > 0\n"
                "          THEN c.criterion_amount * (CAST(:assumed_rate AS DOUBLE) / s.base_hourly_rate)",
            )
        components["query"] = query

    employee_page = next((p for p in spec.get("pages", []) if p.get("name") == "employee_deep_dive"), None)
    if employee_page:
        year_filter = next((w for w in employee_page.get("widgets", []) if w.get("name") == "sim_year"), None)
        if year_filter:
            fields = year_filter.setdefault("fields", [])
            for candidate in (
                {"dataset": "pay_sim_shift_live", "field": "calendar_year"},
                {"dataset": "pay_sim_components_live", "field": "calendar_year"},
            ):
                if candidate not in fields:
                    fields.append(candidate)

        pay_model_filter = next((w for w in employee_page.get("widgets", []) if w.get("name") == "sim_pay_model"), None)
        if pay_model_filter:
            parameters = pay_model_filter.setdefault("parameters", [])
            component_binding = {"dataset": "pay_sim_components_live", "keyword": "pay_model"}
            if component_binding not in parameters:
                parameters.append(component_binding)

        # Keep the visible selector and the parameter defaults identical so the
        # dashboard never opens with an apparently empty control while calculating
        # a hidden default value.
        exact_rate_filter = next((w for w in employee_page.get("widgets", []) if w.get("name") == "sim_exact_rate"), None)
        if exact_rate_filter:
            exact_rate_filter["default_selection"] = _default_values("DECIMAL", "50.00")

        if pay_model_filter:
            pay_model_filter["default_selection"] = _default_values(
                "STRING",
                "BASE_PLUS_SCHADS_MULTIPLIERS",
            )

        # Avoid an ambiguous dashboard text reference when the same parameter name
        # is deliberately bound across several datasets. The calculation summary
        # immediately below displays the exact selected rate and remains the visual
        # source of truth.
        selected_text = next((w for w in employee_page.get("widgets", []) if w.get("name") == "live_sim_selected_rate"), None)
        if selected_text:
            selected_text["text"] = (
                "**Connected simulation state:** the selected hourly rate and pay interpretation below drive "
                "the summary, rate-position, shift and Award-component calculations together."
            )

        component_chart = next((w for w in employee_page.get("widgets", []) if w.get("name") == "sim_components"), None)
        if component_chart:
            component_chart["title"] = "Award Component Requirements / Selected-Base Model"

        component_delta = next((w for w in employee_page.get("widgets", []) if w.get("name") == "sim_component_delta"), None)
        if component_delta:
            component_delta["title"] = "Award Component Amount by Criterion"

        component_table = next((w for w in employee_page.get("widgets", []) if w.get("name") == "sim_component_table"), None)
        if component_table:
            component_table["title"] = "Overtime, Penalties, Breaks and Other Award Components"
            for column in component_table.get("columns", []):
                if column.get("field") == "simulated_component_amount":
                    column["title"] = "Component Comparison Amount"
            component_table["description"] = (
                "Base + SCHADS multipliers scales rate-sensitive Award components using the selected base rate. "
                "Flat/loaded mode keeps the SCHADS component requirement unchanged and tests aggregate pay coverage instead."
            )

        _apply_simulator_language_and_sections(employee_page)

    _assert_live_simulator(spec)
    spec = _apply_current_layout(spec)

    # After the layout finalizer the simulator should be immediately visible at the
    # top of Employee Deep Dive and every legacy six-column page should occupy the
    # modern 12-column Databricks canvas.
    employee_page = next(
        (page for page in spec.get("pages", []) if page.get("name") == "employee_deep_dive"),
        None,
    )
    live_title = next(
        (widget for widget in employee_page.get("widgets", []) if widget.get("name") == "live_sim_title"),
        None,
    ) if employee_page else None
    if live_title is None or live_title.get("position", [0, 99])[1] != 0:
        raise ValueError("AuditHero live simulator was not promoted to the top of Employee Deep Dive")

    return spec