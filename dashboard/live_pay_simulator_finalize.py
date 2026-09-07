from __future__ import annotations


def _default_values(data_type: str, value: str) -> dict:
    return {
        "values": {
            "dataType": data_type,
            "values": [{"value": value}],
        }
    }


def enhance_spec(spec: dict) -> dict:
    datasets = {ds.get("name"): ds for ds in spec.get("datasets", [])}

    for name in ("pay_sim_live", "pay_sim_shift_live"):
        ds = datasets.get(name)
        if not ds:
            continue
        for parameter in ds.get("parameters", []) or []:
            if parameter.get("keyword") == "assumed_rate":
                parameter["displayName"] = parameter.get("displayName") or "Assumed hourly rate"
                parameter["defaultSelection"] = _default_values("DECIMAL", "50.00")
            elif parameter.get("keyword") == "pay_model":
                parameter["displayName"] = parameter.get("displayName") or "Pay interpretation"
                parameter["defaultSelection"] = _default_values("STRING", "BASE_PLUS_SCHADS_MULTIPLIERS")

    for name in ("pay_sim_components_live", "pay_rate_position"):
        ds = datasets.get(name)
        if not ds:
            continue
        for parameter in ds.get("parameters", []) or []:
            if parameter.get("keyword") == "assumed_rate":
                parameter["displayName"] = parameter.get("displayName") or "Assumed hourly rate"
                parameter["defaultSelection"] = _default_values("DECIMAL", "50.00")

    # The component dataset needs a year field so the page-level year filter can
    # constrain the same employee/year across summary, shift and component views.
    components = datasets.get("pay_sim_components_live")
    if components:
        query = components.get("query", "")
        marker = "c.employee_name,\n      c.shift_start,"
        if marker in query and "YEAR(c.shift_start) AS calendar_year" not in query:
            components["query"] = query.replace(
                marker,
                "c.employee_name,\n      YEAR(c.shift_start) AS calendar_year,\n      c.shift_start,",
            )

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

    return spec
