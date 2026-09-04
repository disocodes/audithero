from pathlib import Path

import pandas as pd

from schads_audit.file_readiness import assess_file_readiness


def _write_base(root: Path, *, bad_shift=False, orphan=False, blank_employee=False):
    pd.DataFrame([
        {"employee_id": "" if blank_employee else "E1", "employee_name": "Example Employee", "state": "WA", "work_group": "DISABILITY_SERVICES"}
    ]).to_csv(root / "employees.csv", index=False)
    pd.DataFrame([
        {"employee_id": "E1", "effective_from": "2026-07-01", "classification_code": "HC-DIS-L1-P1"}
    ]).to_csv(root / "pay_details.csv", index=False)
    pd.DataFrame([
        {"employee_id": "E1", "start_date": "2026-07-01", "employment_type": "FULL_TIME"}
    ]).to_csv(root / "employment_history.csv", index=False)
    pd.DataFrame([
        {
            "timesheet_id": "T1",
            "employee_id": "E2" if orphan else "E1",
            "start_datetime": "2026-07-01 09:00",
            "end_datetime": "2026-07-01 08:00" if bad_shift else "2026-07-01 17:00",
            "work_group": "DISABILITY_SERVICES",
            "location_state": "WA",
        }
    ]).to_csv(root / "timesheets.csv", index=False)
    pd.DataFrame([
        {"employee_id": "E1", "effective_from": "2026-07-01", "instrument_type": "AWARD", "award_code": "MA000100"}
    ]).to_csv(root / "industrial_instrument_history.csv", index=False)


def test_readiness_blocks_blank_required_identifiers(tmp_path: Path):
    _write_base(tmp_path, blank_employee=True)
    findings = assess_file_readiness(tmp_path, tmp_path)
    matching = findings[(findings.finding_type == "INPUT_REQUIRED_VALUES") & (findings.source_key == "employees")]
    assert "BLOCKING" in set(matching.status)


def test_readiness_blocks_orphan_employee_references(tmp_path: Path):
    _write_base(tmp_path, orphan=True)
    findings = assess_file_readiness(tmp_path, tmp_path)
    matching = findings[(findings.finding_type == "REFERENTIAL_INTEGRITY") & (findings.source_key == "timesheets.employee_id")]
    assert "BLOCKING" in set(matching.status)


def test_readiness_blocks_end_before_start(tmp_path: Path):
    _write_base(tmp_path, bad_shift=True)
    findings = assess_file_readiness(tmp_path, tmp_path)
    matching = findings[(findings.finding_type == "SHIFT_INTERVAL") & (findings.source_key == "timesheets")]
    assert "BLOCKING" in set(matching.status)
