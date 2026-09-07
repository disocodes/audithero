from __future__ import annotations


def _f(dataset: str, field: str, display_name: str | None = None) -> dict:
    item = {"dataset": dataset, "field": field}
    if display_name:
        item["display_name"] = display_name
    return item


def _p(dataset: str, keyword: str, display_name: str | None = None) -> dict:
    item = {"dataset": dataset, "keyword": keyword}
    if display_name:
        item["display_name"] = display_name
    return item


def _text(name, text, position):
    return {"type": "text", "name": name, "text": text, "position": position}


def _filter(name, title, position, *, dataset=None, field=None, fields=None, parameters=None, selection="single", description=None):
    result = {
        "type": "filter",
        "name": name,
        "title": title,
        "position": position,
        "selection": selection,
    }
    if dataset and field:
        result["dataset"] = dataset
        result["field"] = field
    if fields:
        result["fields"] = fields
    if parameters:
        result["parameters"] = parameters
    if description:
        result["description"] = description
    return result


def _counter(name, dataset, title, expression, position, *, currency=False, decimals=0, description=None):
    result = {
        "type": "counter",
        "name": name,
        "dataset": dataset,
        "title": title,
        "expression": expression,
        "decimals": decimals,
        "position": position,
    }
    if currency:
        result["format"] = "currency"
    if description:
        result["description"] = description
    return result


def _bar(name, dataset, title, x, y_expression, position, *, y_name="value", currency=False, horizontal=False, color=None):
    result = {
        "type": "bar",
        "name": name,
        "dataset": dataset,
        "title": title,
        "x": x,
        "x_title": x.replace("_", " ").title(),
        "y_expression": y_expression,
        "y_name": y_name,
        "y_title": y_name.replace("_", " ").title(),
        "position": position,
    }
    if currency:
        result["format"] = "currency"
        result["decimals"] = 2
    if horizontal:
        result["orientation"] = "horizontal"
    if color:
        result["color"] = color
    return result


def _line(name, dataset, title, x, y_expression, position, *, y_name="value", currency=False):
    result = {
        "type": "line",
        "name": name,
        "dataset": dataset,
        "title": title,
        "x": x,
        "x_title": x.replace("_", " ").title(),
        "x_scale": "quantitative",
        "y_expression": y_expression,
        "y_name": y_name,
        "y_title": y_name.replace("_", " ").title(),
        "position": position,
    }
    if currency:
        result["format"] = "currency"
        result["decimals"] = 2
    return result


def _table(name, dataset, title, position, columns, description=None):
    result = {
        "type": "table",
        "name": name,
        "dataset": dataset,
        "title": title,
        "position": position,
        "columns": columns,
    }
    if description:
        result["description"] = description
    return result


def _parameter(keyword: str, display_name: str, data_type: str, default_selection: dict | None = None):
    return {
        "keyword": keyword,
        "displayName": display_name,
        "dataType": data_type,
        "defaultSelection": default_selection or {},
    }


def _simulation_query(source: str, grain: str) -> str:
    rate = "CAST(:assumed_rate AS DOUBLE)"
    model = "CAST(:pay_model AS STRING)"

    if grain == "employee":
        return f"""
        SELECT
          e.*,
          {rate} AS assumed_rate,
          {model} AS assumed_pay_model,
          CASE
            WHEN {model} = 'FLAT_LOADED_HOURLY'
              THEN e.flat_rate_hours * {rate} + e.fixed_award_amount
            ELSE e.rate_sensitive_factor * {rate} + e.fixed_award_amount
          END AS simulated_pay,
          CASE
            WHEN {model} = 'FLAT_LOADED_HOURLY'
              THEN (e.flat_rate_hours * {rate} + e.fixed_award_amount) - e.award_minimum_entitlement
            ELSE (e.rate_sensitive_factor * {rate} + e.fixed_award_amount) - e.award_minimum_entitlement
          END AS simulated_variance,
          CASE
            WHEN {rate} < e.award_minimum_base_rate - 0.005 THEN 'POTENTIAL_BASE_RATE_UNDERPAYMENT'
            WHEN (
              CASE
                WHEN {model} = 'FLAT_LOADED_HOURLY'
                  THEN e.flat_rate_hours * {rate} + e.fixed_award_amount
                ELSE e.rate_sensitive_factor * {rate} + e.fixed_award_amount
              END
            ) < e.award_minimum_entitlement - 0.05 THEN 'POTENTIAL_UNDERPAYMENT'
            WHEN e.review_shift_count > 0 THEN 'SIMULATION_REQUIRES_AWARD_REVIEW'
            ELSE 'SIMULATION_MEETS_NUMERIC_MINIMUM'
          END AS simulated_status,
          CASE
            WHEN {rate} < e.award_minimum_base_rate - 0.005 THEN
              'Selected rate is below the SCHADS base minimum for this scenario.'
            WHEN (
              CASE
                WHEN {model} = 'FLAT_LOADED_HOURLY'
                  THEN e.flat_rate_hours * {rate} + e.fixed_award_amount
                ELSE e.rate_sensitive_factor * {rate} + e.fixed_award_amount
              END
            ) < e.award_minimum_entitlement - 0.05 THEN
              'Selected rate does not cover the calculated SCHADS entitlement for this roster/scenario.'
            WHEN e.review_shift_count > 0 THEN
              'Numeric pay meets the selected scenario, but Award/evidence findings still require review.'
            ELSE
              'Selected rate meets the calculated numeric minimum for this scenario. This remains hypothetical until payroll evidence is confirmed.'
          END AS simulated_recommendation
        FROM {source} e
        """

    if grain == "shift":
        return f"""
        SELECT
          t.*,
          {rate} AS assumed_rate,
          {model} AS assumed_pay_model,
          CASE
            WHEN {model} = 'FLAT_LOADED_HOURLY'
              THEN t.flat_rate_hours * {rate} + t.fixed_award_amount
            ELSE t.rate_sensitive_factor * {rate} + t.fixed_award_amount
          END AS simulated_shift_pay,
          CASE
            WHEN t.award_minimum_entitlement IS NULL THEN NULL
            WHEN {model} = 'FLAT_LOADED_HOURLY'
              THEN (t.flat_rate_hours * {rate} + t.fixed_award_amount) - t.award_minimum_entitlement
            ELSE (t.rate_sensitive_factor * {rate} + t.fixed_award_amount) - t.award_minimum_entitlement
          END AS simulated_shift_variance
        FROM {source} t
        """

    raise ValueError(grain)


def _component_query() -> str:
    rate = "CAST(:assumed_rate AS DOUBLE)"
    return f"""
    SELECT
      c.audit_run_id,
      c.scenario_id,
      c.classification_family,
      c.scenario_classification_code,
      c.scenario_classification_name,
      c.scenario_level,
      c.scenario_pay_point,
      c.scenario_employment_type,
      c.timesheet_id,
      c.employee_id,
      c.employee_name,
      c.shift_start,
      c.shift_end,
      c.criterion_group,
      c.criterion,
      c.clause,
      c.hours,
      c.multiplier,
      c.effective_hourly_rate,
      c.criterion_amount AS award_component_amount,
      c.day_type,
      c.shift_type,
      c.detail,
      s.base_hourly_rate AS award_minimum_base_rate,
      {rate} AS assumed_rate,
      CASE
        WHEN c.criterion_amount IS NULL THEN NULL
        WHEN UPPER(COALESCE(c.criterion_group,'')) = 'ALLOWANCES'
          OR UPPER(COALESCE(c.criterion,'')) LIKE '%ALLOWANCE%'
          OR UPPER(COALESCE(c.criterion,'')) = 'SLEEPOVER_ALLOWANCE'
          THEN c.criterion_amount
        WHEN s.base_hourly_rate > 0
          THEN c.criterion_amount * ({rate} / s.base_hourly_rate)
        ELSE c.criterion_amount
      END AS simulated_component_amount
    FROM v_award_criteria_detail_latest c
    LEFT JOIN v_award_scenario_detail_latest s
      ON c.audit_run_id = s.audit_run_id
     AND c.scenario_id = s.scenario_id
     AND CAST(c.timesheet_id AS STRING) = CAST(s.timesheet_id AS STRING)
    """


def _rate_position_query() -> str:
    rate = "CAST(:assumed_rate AS DOUBLE)"
    return f"""
    SELECT
      e.audit_run_id,
      e.employee_id,
      e.employee_name,
      e.calendar_year,
      e.scenario_id,
      e.classification_family,
      e.scenario_classification_code,
      e.scenario_classification_name,
      e.scenario_level,
      e.scenario_pay_point,
      e.scenario_employment_type,
      stack(4,
        'SCHADS base minimum', e.award_minimum_base_rate,
        'Award-structure break-even', e.award_structure_break_even_rate,
        'Flat/loaded break-even', e.flat_loaded_break_even_rate,
        'Selected / typed rate', {rate}
      ) AS (rate_marker, rate_value)
    FROM v_pay_simulation_employee_year e
    """


def enhance_spec(spec: dict) -> dict:
    datasets = spec.setdefault("datasets", [])
    existing = {ds.get("name") for ds in datasets}

    if "pay_rate_choices" not in existing:
        datasets.append(
            {
                "name": "pay_rate_choices",
                "display_name": "Hourly Rate Choices (cent precision)",
                "query": "SELECT CAST(id AS DECIMAL(10,2)) / 100 AS assumed_rate FROM range(1, 10001)",
            }
        )

    if "pay_model_choices" not in existing:
        datasets.append(
            {
                "name": "pay_model_choices",
                "display_name": "Pay Model Choices",
                "query": "SELECT * FROM VALUES ('BASE_PLUS_SCHADS_MULTIPLIERS'), ('FLAT_LOADED_HOURLY') AS t(pay_model)",
            }
        )

    common_parameters = [
        _parameter("assumed_rate", "Assumed hourly rate", "DECIMAL"),
        _parameter("pay_model", "Pay interpretation", "STRING"),
    ]
    rate_only = [_parameter("assumed_rate", "Assumed hourly rate", "DECIMAL")]

    additions = [
        {
            "name": "pay_sim_live",
            "display_name": "Live Roster Pay Simulation",
            "query": _simulation_query("v_pay_simulation_employee_year", "employee"),
            "parameters": common_parameters,
        },
        {
            "name": "pay_sim_shift_live",
            "display_name": "Live Shift Pay Simulation",
            "query": _simulation_query("v_pay_simulation_terms_latest", "shift"),
            "parameters": common_parameters,
        },
        {
            "name": "pay_sim_components_live",
            "display_name": "Live Award Component Simulation",
            "query": _component_query(),
            "parameters": rate_only,
        },
        {
            "name": "pay_rate_position",
            "display_name": "Selected Rate Position",
            "query": _rate_position_query(),
            "parameters": rate_only,
        },
    ]
    for dataset in additions:
        if dataset["name"] not in existing:
            datasets.append(dataset)

    global_page = next((p for p in spec.get("pages", []) if p.get("page_type") == "PAGE_TYPE_GLOBAL_FILTERS"), None)
    if global_page is not None:
        mapping = {
            "global_run": "audit_run_id",
            "global_employee": "employee_name",
            "global_stream": "classification_family",
            "global_level": "scenario_level",
            "global_paypoint": "scenario_pay_point",
            "global_emp_type": "scenario_employment_type",
        }
        target_sets = ["pay_sim_live", "pay_sim_shift_live", "pay_sim_components_live", "pay_rate_position"]
        for widget_name, field in mapping.items():
            widget = next((w for w in global_page.get("widgets", []) if w.get("name") == widget_name), None)
            if widget is None:
                continue
            fields = widget.setdefault("fields", [])
            for dataset in target_sets:
                candidate = _f(dataset, field)
                if candidate not in fields:
                    fields.append(candidate)

    page = next((p for p in spec.get("pages", []) if p.get("name") == "employee_deep_dive"), None)
    if page is None or any(w.get("name") == "live_sim_title" for w in page.get("widgets", [])):
        return spec

    page["widgets"].extend(
        [
            _text(
                "live_sim_title",
                "## Live Roster Pay Simulator\nChoose an employee/year/SCHADS scenario with the dashboard filters, then type/search an exact hourly rate (cent precision) and choose how that rate should be interpreted. **Every KPI and detail below uses the same parameter state.** The simulation is not actual-pay evidence until confirmed separately.",
                [0, 44, 6, 3],
            ),
            _filter(
                "sim_year",
                "Simulation Year",
                [0, 47, 1, 1],
                fields=[_f("pay_sim_live", "calendar_year"), _f("pay_rate_position", "calendar_year")],
                selection="single",
            ),
            _filter(
                "sim_scenario",
                "SCHADS Scenario",
                [1, 47, 2, 1],
                fields=[
                    _f("pay_sim_live", "scenario_classification_name"),
                    _f("pay_sim_shift_live", "scenario_classification_name"),
                    _f("pay_sim_components_live", "scenario_classification_name"),
                    _f("pay_rate_position", "scenario_classification_name"),
                ],
                selection="single",
            ),
            _filter(
                "sim_exact_rate",
                "Assumed Hourly Rate (type/search exact cents)",
                [3, 47, 2, 1],
                fields=[_f("pay_rate_choices", "assumed_rate")],
                parameters=[
                    _p("pay_sim_live", "assumed_rate"),
                    _p("pay_sim_shift_live", "assumed_rate"),
                    _p("pay_sim_components_live", "assumed_rate"),
                    _p("pay_rate_position", "assumed_rate"),
                ],
                selection="single",
                description="One authoritative rate parameter. Type part/all of a cent-precision value, then select it. This updates every simulation widget below.",
            ),
            _filter(
                "sim_pay_model",
                "Pay Interpretation",
                [5, 47, 1, 1],
                fields=[_f("pay_model_choices", "pay_model")],
                parameters=[_p("pay_sim_live", "pay_model"), _p("pay_sim_shift_live", "pay_model")],
                selection="single",
                description="Base + SCHADS multipliers treats the selected rate as base pay. Flat/loaded treats it as a flat rate across rostered worked hours plus fixed Award components.",
            ),
            _text(
                "live_sim_selected_rate",
                "**Current simulation:** $@assumed_rate/hour · @pay_model",
                [0, 48, 6, 1],
            ),
            _counter("sim_selected_rate_kpi", "pay_sim_live", "Selected Hourly Rate", "MAX(`assumed_rate`)", [0, 49, 1, 2], currency=True, decimals=2),
            _counter("sim_award_base", "pay_sim_live", "SCHADS Base Minimum", "MAX(`award_minimum_base_rate`)", [1, 49, 1, 2], currency=True, decimals=2),
            _counter("sim_award_total", "pay_sim_live", "SCHADS Roster Entitlement", "MAX(`award_minimum_entitlement`)", [2, 49, 1, 2], currency=True, decimals=2),
            _counter("sim_total", "pay_sim_live", "Simulated Pay", "MAX(`simulated_pay`)", [3, 49, 1, 2], currency=True, decimals=2),
            _counter("sim_variance", "pay_sim_live", "Simulated Variance", "MAX(`simulated_variance`)", [4, 49, 1, 2], currency=True, decimals=2),
            _counter("sim_review_shifts", "pay_sim_live", "Review Shifts", "MAX(`review_shift_count`)", [5, 49, 1, 2]),
            _bar(
                "sim_rate_position",
                "pay_rate_position",
                "Selected Rate vs SCHADS / Break-even Rates",
                "rate_marker",
                "MAX(`rate_value`)",
                [0, 51, 3, 7],
                y_name="hourly_rate",
                currency=True,
                horizontal=True,
                color="rate_marker",
            ),
            _bar(
                "sim_components",
                "pay_sim_components_live",
                "Simulated Pay by Award Component",
                "criterion_group",
                "SUM(COALESCE(`simulated_component_amount`,0))",
                [3, 51, 3, 7],
                y_name="simulated_amount",
                currency=True,
                horizontal=True,
            ),
            _bar(
                "sim_shift_variance",
                "pay_sim_shift_live",
                "Shift Variance at Selected Rate",
                "shift_start",
                "SUM(COALESCE(`simulated_shift_variance`,0))",
                [0, 58, 3, 7],
                y_name="variance",
                currency=True,
            ),
            _bar(
                "sim_component_delta",
                "pay_sim_components_live",
                "Selected-Rate Component Amount by Criterion",
                "criterion",
                "SUM(COALESCE(`simulated_component_amount`,0))",
                [3, 58, 3, 7],
                y_name="simulated_amount",
                currency=True,
                horizontal=True,
            ),
            _table(
                "sim_summary_table",
                "pay_sim_live",
                "Live Employee / Scenario Simulation",
                [0, 65, 6, 7],
                [
                    {"field": "employee_name", "title": "Employee"},
                    {"field": "calendar_year", "title": "Year", "kind": "integer"},
                    {"field": "scenario_classification_name", "title": "SCHADS Scenario"},
                    {"field": "scenario_employment_type", "title": "Employment Type"},
                    {"field": "assumed_rate", "title": "Selected Rate", "kind": "number", "number_format": "$0.00"},
                    {"field": "assumed_pay_model", "title": "Pay Interpretation"},
                    {"field": "award_minimum_base_rate", "title": "SCHADS Base", "kind": "number", "number_format": "$0.00"},
                    {"field": "award_structure_break_even_rate", "title": "Award-Structure Break-even", "kind": "number", "number_format": "$0.00"},
                    {"field": "flat_loaded_break_even_rate", "title": "Flat Break-even", "kind": "number", "number_format": "$0.00"},
                    {"field": "award_minimum_entitlement", "title": "SCHADS Entitlement", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "simulated_pay", "title": "Simulated Pay", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "simulated_variance", "title": "Variance", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "simulated_status", "title": "Simulation Status"},
                    {"field": "simulated_recommendation", "title": "Recommendation"},
                ],
                description="This is what-if analysis from roster evidence. Use AuditHero - Confirm Employee Pay Rate to persist reviewed rate evidence; upload payroll for definitive actual-versus-expected reconciliation.",
            ),
            _table(
                "sim_shift_table",
                "pay_sim_shift_live",
                "Shift-by-Shift Simulation",
                [0, 72, 6, 9],
                [
                    {"field": "shift_start", "title": "Shift Start"},
                    {"field": "shift_end", "title": "Shift End"},
                    {"field": "roster_worked_hours", "title": "Roster Hours", "kind": "number"},
                    {"field": "award_minimum_base_rate", "title": "SCHADS Base", "kind": "number", "number_format": "$0.00"},
                    {"field": "award_minimum_entitlement", "title": "SCHADS Shift Entitlement", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "assumed_rate", "title": "Selected Rate", "kind": "number", "number_format": "$0.00"},
                    {"field": "simulated_shift_pay", "title": "Simulated Shift Pay", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "simulated_shift_variance", "title": "Variance", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "review_flags", "title": "Award / Evidence Findings"},
                ],
            ),
            _table(
                "sim_component_table",
                "pay_sim_components_live",
                "Overtime, Penalties, Breaks and Other Award Components",
                [0, 81, 6, 10],
                [
                    {"field": "shift_start", "title": "Shift"},
                    {"field": "criterion_group", "title": "Audit Area"},
                    {"field": "criterion", "title": "Component / Finding"},
                    {"field": "hours", "title": "Hours", "kind": "number"},
                    {"field": "multiplier", "title": "Multiplier", "kind": "number"},
                    {"field": "award_component_amount", "title": "SCHADS Amount", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "simulated_component_amount", "title": "Selected-Rate Amount", "kind": "number", "number_format": "$0,0.00"},
                    {"field": "clause", "title": "Clause"},
                    {"field": "day_type", "title": "Day Type"},
                    {"field": "shift_type", "title": "Shift Type"},
                    {"field": "detail", "title": "Evidence", "kind": "json"},
                ],
            ),
        ]
    )
    return spec
