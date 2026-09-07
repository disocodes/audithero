from __future__ import annotations


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

        # Avoid an ambiguous dashboard text reference when the same parameter name
        # is deliberately bound across several datasets. The KPI immediately below
        # displays the exact selected rate and therefore remains the visual source
        # of truth.
        selected_text = next((w for w in employee_page.get("widgets", []) if w.get("name") == "live_sim_selected_rate"), None)
        if selected_text:
            selected_text["text"] = (
                "**Connected simulation state:** the selected hourly rate and pay interpretation below drive "
                "the summary, rate-position, shift and Award-component views together."
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

    return spec
