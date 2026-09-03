from __future__ import annotations
import json
import secrets


def _id():
    return secrets.token_hex(10)


def _measure_select(entity, source, measure):
    return {
        "Measure": {
            "Expression": {"SourceRef": {"Source": source}},
            "Property": measure,
        },
        "Name": f"{entity}.{measure}",
        "NativeReferenceName": measure,
    }


def _column_select(entity, source, column):
    return {
        "Column": {
            "Expression": {"SourceRef": {"Source": source}},
            "Property": column,
        },
        "Name": f"{entity}.{column}",
        "NativeReferenceName": column,
    }


def _container(config, x, y, w, h, z):
    return {
        "config": json.dumps(config, separators=(",", ":")),
        "filters": "[]",
        "height": float(h),
        "width": float(w),
        "x": float(x),
        "y": float(y),
        "z": float(z),
    }


def _title(entity, text, x=20, y=10, w=1240, h=48, z=0):
    return _matrix(entity, [], title=text, x=x, y=y, w=w, h=h, z=z)


def _card(entity, measures, x=20, y=130, w=1240, h=145, z=100, title="AuditHero — SCHADS Payroll Compliance"):
    vid = _id()
    source = "r"
    query_refs = [f"{entity}.{m}" for m in measures]
    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z}}],
        "singleVisual": {
            "visualType": "multiRowCard",
            "projections": {"Values": [{"queryRef": q} for q in query_refs]},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": source, "Entity": entity, "Type": 0}],
                "Select": [_measure_select(entity, source, m) for m in measures],
            },
            "drillFilterOtherVisuals": True,
            "hasDefaultSort": True,
            "objects": {
                "categoryLabels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "fontSize": {"expr": {"Literal": {"Value": "10D"}}}}}],
                "dataLabels": [{"properties": {"fontSize": {"expr": {"Literal": {"Value": "17D"}}}, "bold": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
            "vcObjects": {
                "title": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}}}}]
            },
        },
    }
    return _container(config, x, y, w, h, z)


def _matrix(entity, columns, measures=None, title=None, x=20, y=285, w=1240, h=410, z=1000):
    measures = measures or []
    vid = _id()
    source = "t"
    row_refs = [f"{entity}.{c}" for c in columns]
    value_refs = [f"{entity}.{m}" for m in measures]
    projections = {"Rows": [{"queryRef": q} for q in row_refs]}
    if value_refs:
        projections["Values"] = [{"queryRef": q} for q in value_refs]
    selects = [_column_select(entity, source, c) for c in columns]
    selects += [_measure_select(entity, source, m) for m in measures]
    single = {
        "visualType": "pivotTable",
        "projections": projections,
        "prototypeQuery": {
            "Version": 2,
            "From": [{"Name": source, "Entity": entity, "Type": 0}],
            "Select": selects,
        },
        "drillFilterOtherVisuals": True,
        "hasDefaultSort": True,
        "vcObjects": {
            "title": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "text": {"expr": {"Literal": {"Value": "'" + (title or entity).replace("'", "''") + "'"}}}}}]
        },
    }
    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z}}],
        "singleVisual": single,
    }
    return _container(config, x, y, w, h, z)


def _slicer(entity, column, title, x, y=55, w=195, h=68, z=50, mode="Dropdown"):
    """Create an interactive PBIR-Legacy dropdown slicer."""
    vid = _id()
    source = "s"
    query_ref = f"{entity}.{column}"
    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z}}],
        "singleVisual": {
            "visualType": "slicer",
            "projections": {"Values": [{"queryRef": query_ref, "active": True}]},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": source, "Entity": entity, "Type": 0}],
                "Select": [_column_select(entity, source, column)],
            },
            "drillFilterOtherVisuals": True,
            "objects": {
                "data": [{"properties": {"mode": {"expr": {"Literal": {"Value": f"'{mode}'"}}}}}],
                "header": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}}}}],
                "selection": [{"properties": {"singleSelect": {"expr": {"Literal": {"Value": "false"}}}}}],
            },
        },
    }
    return _container(config, x, y, w, h, z)


def _scenario_slicers(entity, *, y=55):
    fields = [
        ("employee_name", "Employee", 20, 230),
        ("classification_family", "SCHADS Stream", 260, 190),
        ("scenario_level", "Level", 460, 135),
        ("scenario_pay_point", "Pay Point", 605, 135),
        ("scenario_employment_type", "Employment Type", 750, 195),
    ]
    return [_slicer(entity, column, title, x, y=y, w=w, z=50+i) for i, (column, title, x, w) in enumerate(fields)]


def _criteria_slicers(entity, *, y=55):
    return _scenario_slicers(entity, y=y)


def _section(name, visuals, height=720):
    return {
        "config": "{\"filterSortOrder\":3}",
        "displayName": name,
        "displayOption": 1,
        "filters": "[]",
        "height": float(height),
        "name": _id(),
        "visualContainers": visuals,
        "width": 1280.0,
    }


def build_audithero_report_json():
    """Return AuditHero's interactive PBIR-Legacy report definition."""
    award_explorer = _section(
        "Award Explorer",
        [
            *_scenario_slicers("Award Scenarios"),
            _card(
                "Award Scenarios",
                ["Scenario Shift Rows", "Scenario Employees", "Scenario Expected Pay", "Below Minimum Rate Rows", "Scenario Review Shifts", "Explicit Shift Shortfall"],
                y=135,
                title="SCHADS Award Explorer — selected scenario",
            ),
            _matrix(
                "Award Scenarios",
                [
                    "employee_name", "shift_start", "shift_end", "classification_family",
                    "scenario_level", "scenario_pay_point", "scenario_employment_type",
                    "base_hourly_rate", "supplied_base_hourly_rate", "base_rate_status",
                    "expected_amount", "observed_shift_pay", "scenario_status", "review_flags",
                ],
                title="Scenario shift results — change the slicers to compare SCHADS levels and employment types",
                y=295,
                h=400,
            ),
        ],
    )

    historical_rates = _section(
        "Classification & Historical Rates",
        [
            *_scenario_slicers("Award Scenarios"),
            _slicer("Award Scenarios", "base_rate_status", "Rate Status", 955, y=55, w=170, z=60),
            _card(
                "Award Scenarios",
                ["Below Minimum Rate Rows", "At Minimum Rate Rows", "Above Minimum Rate Rows", "Rate Not Supplied Rows", "Base Rate Shortfall Estimate"],
                y=135,
                title="Effective-dated base-rate compliance",
            ),
            _matrix(
                "Award Scenarios",
                [
                    "employee_name", "shift_start", "source_rate_effective_from",
                    "source_rate_reference", "source_classification_name",
                    "classification_family", "scenario_level", "scenario_pay_point",
                    "supplied_base_hourly_rate", "base_hourly_rate", "base_rate_variance",
                    "base_rate_status",
                ],
                title="Employee rate history aligned to each audited shift date",
                y=295,
                h=400,
            ),
        ],
    )

    penalties = _section(
        "Penalties & Shiftwork",
        [
            *_criteria_slicers("Penalties & Shiftwork"),
            _slicer("Penalties & Shiftwork", "criterion", "Award Component", 955, y=55, w=220, z=60),
            _card(
                "Penalties & Shiftwork",
                ["Award Components", "Criterion Hours", "Criterion Amount"],
                y=135,
                title="Penalties, shiftwork, public holidays and minimum engagement",
            ),
            _matrix(
                "Penalties & Shiftwork",
                [
                    "employee_name", "shift_start", "scenario_classification_code",
                    "scenario_employment_type", "criterion_group", "criterion", "day_type",
                    "shift_type", "hours", "multiplier", "effective_hourly_rate",
                    "criterion_amount", "clause", "detail",
                ],
                title="SCHADS penalty and shiftwork calculation components",
                y=295,
                h=400,
            ),
        ],
    )

    overtime = _section(
        "Overtime",
        [
            *_criteria_slicers("Overtime Criteria"),
            _slicer("Overtime Criteria", "criterion", "Overtime Rule", 955, y=55, w=220, z=60),
            _card(
                "Overtime Criteria",
                ["Award Components", "Criterion Hours", "Criterion Amount"],
                y=135,
                title="SCHADS overtime calculation",
            ),
            _matrix(
                "Overtime Criteria",
                [
                    "employee_name", "shift_start", "scenario_classification_code",
                    "scenario_employment_type", "criterion", "hours", "multiplier",
                    "effective_hourly_rate", "criterion_amount", "clause", "detail",
                ],
                title="Overtime components and evidence",
                y=295,
                h=400,
            ),
        ],
    )

    rest_meal = _section(
        "Rest & Meal Breaks",
        [
            _slicer("Award Scenario Rest", "employee_name", "Employee", 20, y=45, w=245),
            _slicer("Award Scenario Rest", "scenario_level", "Level", 275, y=45, w=140),
            _slicer("Award Scenario Rest", "scenario_pay_point", "Pay Point", 425, y=45, w=140),
            _slicer("Award Scenario Rest", "scenario_employment_type", "Employment Type", 575, y=45, w=205),
            _slicer("Award Scenario Rest", "status", "Finding Status", 790, y=45, w=190),
            _card(
                "Award Scenario Rest",
                ["Scenario Rest Intervals", "Scenario Short Rest", "Scenario Rest Shortfall Hours", "Scenario Rest Review", "Scenario Double-Time Hours", "Scenario Double-Time Top-up"],
                y=125,
                title="Rest between work — required break and payment consequences",
            ),
            _matrix(
                "Award Scenario Rest",
                [
                    "employee_name", "previous_shift_end", "next_shift_start",
                    "required_rest_hours", "actual_rest_hours", "rest_shortfall_hours",
                    "overtime_rest_rule_applies", "employer_instructed_resume",
                    "release_datetime", "double_time_repriced_hours", "double_time_topup",
                    "payment_status", "status", "clause", "overtime_clause", "notes",
                ],
                title="Rest-between-work findings",
                y=285,
                h=255,
            ),
            _matrix(
                "Meal Break Criteria",
                [
                    "employee_name", "shift_start", "scenario_classification_code",
                    "scenario_employment_type", "criterion", "hours", "effective_hourly_rate",
                    "criterion_amount", "clause", "detail",
                ],
                ["Award Components", "Criterion Hours", "Criterion Amount"],
                title="Meal-break criteria and evidence findings",
                y=550,
                h=155,
                z=2000,
            ),
        ],
    )

    sleep_broken = _section(
        "Sleepovers, Broken Shifts & Allowances",
        [
            *_criteria_slicers("Sleepover Broken Shift & Allowances"),
            _slicer("Sleepover Broken Shift & Allowances", "criterion_group", "Criteria Area", 955, y=55, w=220, z=60),
            _card(
                "Sleepover Broken Shift & Allowances",
                ["Award Components", "Criterion Hours", "Criterion Amount"],
                y=135,
                title="Sleepovers, broken shifts, minimum engagement and allowances",
            ),
            _matrix(
                "Sleepover Broken Shift & Allowances",
                [
                    "employee_name", "shift_start", "scenario_classification_code",
                    "scenario_employment_type", "criterion_group", "criterion", "hours",
                    "multiplier", "effective_hourly_rate", "criterion_amount", "clause", "detail",
                ],
                title="Calculated components and supporting evidence",
                y=295,
                h=400,
            ),
        ],
    )

    actual_expected = _section(
        "Actual vs Expected",
        [
            _slicer("Pay Period Reconciliation", "employee_name", "Employee", 20, y=45, w=260),
            _slicer("Pay Period Reconciliation", "status", "Audit Status", 290, y=45, w=200),
            _card(
                "Pay Period Reconciliation",
                [
                    "Employees Audited", "Pay Periods", "Underpaid Periods", "Overpaid Periods",
                    "Requires Review Periods", "Actual Pay Unavailable Periods",
                    "Potential Underpayment", "Potential Overpayment",
                ],
                y=125,
                title="Definitive actual-pay reconciliation",
            ),
            _matrix(
                "Pay Period Reconciliation",
                ["employee_name", "pay_period_start", "pay_period_end", "status", "unmapped_pay_categories"],
                ["Expected Pay", "Actual Auditable Pay", "Net Variance"],
                title="Expected versus actual pay — definitive only when usable payroll evidence exists",
                y=285,
                h=410,
            ),
        ],
    )

    evidence = _section(
        "Evidence Required",
        [
            _slicer("Evidence Required", "employee_name", "Employee", 20, y=45, w=250),
            _slicer("Evidence Required", "criterion_group", "Audit Area", 280, y=45, w=220),
            _slicer("Evidence Required", "scenario_level", "Level", 510, y=45, w=140),
            _slicer("Evidence Required", "scenario_employment_type", "Employment Type", 660, y=45, w=220),
            _card("Evidence Required", ["Evidence Findings"], y=125, title="Evidence needed to make affected findings definitive"),
            _matrix(
                "Evidence Required",
                [
                    "employee_name", "shift_start", "scenario_classification_code",
                    "scenario_employment_type", "criterion_group", "detail",
                ],
                title="Employee / shift evidence required",
                y=285,
                h=250,
            ),
            _matrix(
                "Readiness Findings",
                ["finding_type", "source_label", "status", "detail", "checked_at"],
                title="Source-level readiness findings",
                y=545,
                h=150,
                z=2000,
            ),
        ],
    )

    definitive = _section(
        "Definitive Shift Investigation",
        [
            _slicer("Audit Detail", "employee_name", "Employee", 20, y=45, w=260),
            _slicer("Audit Detail", "employment_type", "Employment Type", 290, y=45, w=210),
            _slicer("Audit Detail", "classification_code", "Classification", 510, y=45, w=240),
            _slicer("Audit Detail", "entitlement_status", "Shift Status", 760, y=45, w=200),
            _card("Audit Detail", ["Shifts Audited", "Review Shifts", "Expected Shift Entitlements"], y=125, title="Definitive shift audit from known employee facts"),
            _matrix(
                "Audit Detail",
                [
                    "employee_name", "shift_start", "shift_end", "employment_type",
                    "classification_code", "work_group", "state", "worked_hours",
                    "base_hourly_rate", "expected_amount", "entitlement_status",
                    "review_flags", "calculation_evidence",
                ],
                title="Shift-level SCHADS calculation evidence",
                y=285,
                h=410,
            ),
        ],
    )

    controls = _section(
        "Rules & Audit History",
        [
            _matrix(
                "Audit Runs",
                ["finished_at", "run_type", "audit_window_start", "audit_window_end", "status", "actual_pay_source", "employees", "timesheets", "message"],
                title="Audit run history",
                y=20,
                h=315,
            ),
            _matrix(
                "Rule Coverage",
                ["pack_type", "classification_family", "pack_id", "operative_date", "verification_status", "source_publisher", "source_url"],
                title="Effective-dated SCHADS rule library",
                y=350,
                h=345,
                z=2000,
            ),
        ],
    )

    return {
        "config": json.dumps(
            {
                "version": "5.55",
                "themeCollection": {"baseTheme": {"name": "CY24SU06", "version": "5.56", "type": 2}},
                "activeSectionIndex": 0,
                "defaultDrillFilterOtherVisuals": True,
                "filterSortOrder": 3,
                "settings": {
                    "useNewFilterPaneExperience": True,
                    "allowChangeFilterTypes": True,
                    "useEnhancedTooltips": True,
                    "exportDataMode": 1,
                },
            },
            separators=(",", ":"),
        ),
        "filters": "[]",
        "layoutOptimization": 0,
        "resourcePackages": [
            {"resourcePackage": {"disabled": False, "items": [{"name": "CY24SU06", "path": "BaseThemes/CY24SU06.json", "type": 202}], "name": "SharedResources", "type": 2}}
        ],
        "sections": [
            award_explorer,
            historical_rates,
            penalties,
            overtime,
            rest_meal,
            sleep_broken,
            actual_expected,
            evidence,
            definitive,
            controls,
        ],
    }
