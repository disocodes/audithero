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


def _card(entity, measures, x=20, y=20, w=1240, h=165, z=0, title="AuditHero — SCHADS Payroll Compliance"):
    vid = _id()
    source = "r"
    query_refs = [f"{entity}.{m}" for m in measures]
    config = {
        "name": vid,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x,
                    "y": y,
                    "z": z,
                    "width": w,
                    "height": h,
                    "tabOrder": z,
                },
            }
        ],
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
                "categoryLabels": [
                    {
                        "properties": {
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "fontSize": {"expr": {"Literal": {"Value": "11D"}}},
                        }
                    }
                ],
                "dataLabels": [
                    {
                        "properties": {
                            "fontSize": {"expr": {"Literal": {"Value": "18D"}}},
                            "bold": {"expr": {"Literal": {"Value": "true"}}},
                        }
                    }
                ],
            },
            "vcObjects": {
                "title": [
                    {
                        "properties": {
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}},
                        }
                    }
                ]
            },
        },
    }
    return _container(config, x, y, w, h, z)


def _matrix(entity, columns, measures=None, title=None, x=20, y=200, w=1240, h=500, z=1000):
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
            "title": [
                {
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {
                            "expr": {
                                "Literal": {
                                    "Value": "'" + (title or entity).replace("'", "''") + "'"
                                }
                            }
                        },
                    }
                }
            ]
        },
    }
    config = {
        "name": vid,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x,
                    "y": y,
                    "z": z,
                    "width": w,
                    "height": h,
                    "tabOrder": z,
                },
            }
        ],
        "singleVisual": single,
    }
    return _container(config, x, y, w, h, z)


def _section(name, visuals):
    return {
        "config": "{\"filterSortOrder\":3}",
        "displayName": name,
        "displayOption": 1,
        "filters": "[]",
        "height": 720.0,
        "name": _id(),
        "visualContainers": visuals,
        "width": 1280.0,
    }


def build_audithero_report_json():
    """Return a PBIR-Legacy report definition deployable through Fabric REST."""
    overview = _section(
        "Payroll Overview",
        [
            _card(
                "Pay Period Reconciliation",
                [
                    "Employees Audited",
                    "Pay Periods",
                    "Underpaid Periods",
                    "Overpaid Periods",
                    "Requires Review Periods",
                    "Potential Underpayment",
                    "Potential Overpayment",
                    "Compliance Rate",
                ],
            ),
            _matrix(
                "Pay Period Reconciliation",
                ["employee_name", "pay_period_start", "pay_period_end", "status"],
                ["Expected Pay", "Actual Auditable Pay", "Net Variance"],
                title="Current audit — employee pay periods",
            ),
        ],
    )
    exceptions = _section(
        "Exceptions",
        [
            _matrix(
                "Pay Period Reconciliation",
                [
                    "employee_name",
                    "pay_period_start",
                    "pay_period_end",
                    "status",
                    "unmapped_pay_categories",
                ],
                ["Expected Pay", "Actual Auditable Pay", "Net Variance"],
                title="Underpayment / overpayment / review queue",
                y=25,
                h=660,
            )
        ],
    )
    shifts = _section(
        "Shift Evidence",
        [
            _matrix(
                "Audit Detail",
                [
                    "employee_name",
                    "shift_start",
                    "shift_end",
                    "employment_type",
                    "classification_code",
                    "work_group",
                    "state",
                    "worked_hours",
                    "expected_amount",
                    "entitlement_status",
                    "review_flags",
                ],
                title="Shift-level SCHADS calculation evidence",
                y=25,
                h=660,
            )
        ],
    )
    rest_breaks = _section(
        "Rest & Breaks",
        [
            _card(
                "Rest Break Findings",
                [
                    "Rest Intervals Assessed",
                    "Short Rest Findings",
                    "Rest Findings Requiring Review",
                    "Overtime Rest Cases",
                    "Double-Time Repriced Hours",
                    "Double-Time Top-up",
                    "Paid Absence Rostered Hours",
                ],
                y=20,
                h=165,
                title="AuditHero — Rest Between Work",
            ),
            _matrix(
                "Rest Break Findings",
                [
                    "employee_name",
                    "previous_shift_end",
                    "next_shift_start",
                    "required_rest_hours",
                    "actual_rest_hours",
                    "rest_shortfall_hours",
                    "status",
                    "sleepover_adjacent_exception_eligible",
                    "sleepover_8h_agreement",
                    "overtime_rest_rule_applies",
                    "employer_instructed_resume",
                    "release_datetime",
                    "double_time_repriced_hours",
                    "double_time_topup",
                    "paid_absence_rostered_hours",
                    "payment_status",
                    "clause",
                    "overtime_clause",
                    "evidence_reference",
                    "notes",
                ],
                title="Effective-dated rest-between-work findings",
                y=200,
                h=485,
            ),
        ],
    )
    supplemental = _section(
        "Supplemental & TOIL",
        [
            _matrix(
                "Supplemental Entitlements",
                [
                    "employee_name",
                    "event_type",
                    "pay_period_start",
                    "pay_period_end",
                    "expected_adjustment",
                    "event_status",
                    "review_flags",
                ],
                title="On-call, recall, remote work, higher duties and other controlled events",
                y=25,
                h=315,
            ),
            _matrix(
                "TOIL Findings",
                [
                    "employee_name",
                    "overtime_datetime",
                    "overtime_hours",
                    "time_off_hours",
                    "remaining_hours",
                    "deadline",
                    "payment_reason",
                    "expected_adjustment",
                    "status",
                    "review_flags",
                ],
                title="Time off instead of overtime register",
                y=365,
                h=320,
                z=2000,
            ),
        ],
    )
    controls = _section(
        "Controls & Rules",
        [
            _matrix(
                "Readiness Findings",
                ["finding_type", "source_label", "status", "detail", "checked_at"],
                title="Audit readiness and mapping controls",
                y=25,
                h=310,
            ),
            _matrix(
                "Rule Coverage",
                [
                    "pack_type",
                    "classification_family",
                    "pack_id",
                    "operative_date",
                    "verification_status",
                    "source_url",
                ],
                title="Effective-dated SCHADS rule library",
                y=360,
                h=325,
                z=2000,
            ),
        ],
    )
    return {
        "config": json.dumps(
            {
                "version": "5.55",
                "themeCollection": {
                    "baseTheme": {"name": "CY24SU06", "version": "5.56", "type": 2}
                },
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
            {
                "resourcePackage": {
                    "disabled": False,
                    "items": [
                        {"name": "CY24SU06", "path": "BaseThemes/CY24SU06.json", "type": 202}
                    ],
                    "name": "SharedResources",
                    "type": 2,
                }
            }
        ],
        "sections": [overview, exceptions, shifts, rest_breaks, supplemental, controls],
    }
