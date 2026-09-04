from __future__ import annotations

import pandas as pd

from . import award_scenarios as _scenario_module
from .scenario_engine import build_holiday_lookup, calculate_scenario_entitlements


def calculate_award_scenarios(
    employees: pd.DataFrame,
    timesheets: pd.DataFrame,
    holidays: pd.DataFrame,
    lib,
    **kwargs,
) -> dict[str, pd.DataFrame]:
    """Run the complete Award scenario matrix using the fast synthetic resolver.

    The existing scenario pipeline remains authoritative for overtime, broken
    shifts, sleepovers, part-time checks, meal breaks, rest-between-work,
    criteria generation and scenario metadata. Only the generic entitlement
    resolver is replaced while the matrix is running because scenario inputs
    already provide a single synthetic classification and employment type.
    """
    holiday_lookup = build_holiday_lookup(holidays)
    original = _scenario_module.calculate_entitlements

    def _fast_entitlements(
        scenario_employees,
        synthetic_history,
        synthetic_pay,
        scenario_timesheets,
        scenario_holidays,
        scenario_lib,
    ):
        classification_code = ""
        if synthetic_pay is not None and not synthetic_pay.empty and "classification_code" in synthetic_pay.columns:
            value = synthetic_pay["classification_code"].iloc[0]
            classification_code = "" if pd.isna(value) else str(value)

        employment_type = "UNKNOWN"
        if synthetic_history is not None and not synthetic_history.empty and "employment_type" in synthetic_history.columns:
            value = synthetic_history["employment_type"].iloc[0]
            employment_type = "UNKNOWN" if pd.isna(value) else str(value)

        return calculate_scenario_entitlements(
            scenario_employees,
            scenario_timesheets,
            scenario_holidays,
            scenario_lib,
            classification_code=classification_code,
            employment_type=employment_type,
            holiday_lookup=holiday_lookup,
        )

    _scenario_module.calculate_entitlements = _fast_entitlements
    try:
        return _scenario_module.calculate_award_scenarios(
            employees,
            timesheets,
            holidays,
            lib,
            **kwargs,
        )
    finally:
        _scenario_module.calculate_entitlements = original
