import pandas as pd

from schads_audit.manual_audit import _usable_actual_pay
from schads_audit.normalize import normalize_payroll_earnings


def _payroll():
    return pd.DataFrame([
        {
            "employee_id": "E1",
            "pay_period_start": "2026-07-01",
            "pay_period_end": "2026-07-14",
            "pay_category": "Ordinary Hours",
            "amount": 1000.0,
        }
    ])


def _mapping():
    return {"Ordinary Hours": {"audit_treatment": "AUDITABLE_WORK"}}


def test_actual_pay_requires_complete_payroll_and_mapping():
    assert _usable_actual_pay(_payroll(), _mapping()) is True
    assert _usable_actual_pay(pd.DataFrame(), _mapping()) is False
    assert _usable_actual_pay(_payroll(), {}) is False


def test_actual_pay_requires_joinable_employee_ids():
    assert _usable_actual_pay(_payroll(), _mapping(), {"E1"}) is True
    assert _usable_actual_pay(_payroll(), _mapping(), {"E2"}) is False


def test_actual_pay_requires_every_pay_category_to_be_controlled():
    payroll = pd.concat([
        _payroll(),
        pd.DataFrame([{
            "employee_id": "E1",
            "pay_period_start": "2026-07-01",
            "pay_period_end": "2026-07-14",
            "pay_category": "Mystery Item",
            "amount": 25.0,
        }]),
    ], ignore_index=True)
    assert _usable_actual_pay(payroll, _mapping(), {"E1"}) is False


def test_actual_pay_missing_amount_is_not_interpreted_as_zero():
    payroll = _payroll()
    payroll.loc[0, "amount"] = None
    assert _usable_actual_pay(payroll, _mapping(), {"E1"}) is False

    normalized = normalize_payroll_earnings([
        {
            "EmployeeId": "E1",
            "PayPeriodStarting": "2026-07-01",
            "PayPeriodEnding": "2026-07-14",
            "PayCategoryName": "Ordinary Hours",
        }
    ])
    assert pd.isna(normalized.loc[0, "amount"])


def test_actual_pay_blank_required_values_are_rejected():
    payroll = _payroll()
    payroll.loc[0, "pay_category"] = " "
    assert _usable_actual_pay(payroll, _mapping(), {"E1"}) is False
