from pathlib import Path
import json
import pandas as pd

from schads_audit.source_mapping import generate_mapping_draft, convert_source_files


def test_generate_mapping_draft_and_convert(tmp_path: Path):
    pd.DataFrame([
        {"Employee Number": "E1", "First Name": "Ada", "Last Name": "Example", "Employment Status": "Casual", "Work State": "WA"}
    ]).to_csv(tmp_path / "employees_export.csv", index=False)
    pd.DataFrame([
        {"Employee Number": "E1", "Effective Date": "2026-07-01", "AuditHero Classification Code": "SACS-L2-P3"}
    ]).to_csv(tmp_path / "classifications.csv", index=False)
    pd.DataFrame([
        {"Employee Number": "E1", "Start Date": "2024-01-01", "Employment Type": "Casual"}
    ]).to_csv(tmp_path / "employment_history.csv", index=False)
    pd.DataFrame([
        {"Entry ID": "T1", "Employee Number": "E1", "Shift Date": "2026-08-01", "Start Time": "08:00", "End Time": "12:00"}
    ]).to_csv(tmp_path / "timesheets.csv", index=False)

    draft = generate_mapping_draft(tmp_path)
    assert "employees" in draft["datasets"]

    mapping = {
        "version": 1,
        "datasets": {
            "employees": {
                "enabled": True,
                "source": {"file": "employees_export.csv"},
                "columns": {
                    "employee_id": {"source": "Employee Number"},
                    "employee_name": {"concat": ["First Name", "Last Name"]},
                    "employment_type_current": {"source": "Employment Status", "value_map": {"Casual": "CASUAL"}},
                    "state": {"source": "Work State"},
                },
            },
            "pay_details": {
                "enabled": True,
                "source": {"file": "classifications.csv"},
                "columns": {
                    "employee_id": {"source": "Employee Number"},
                    "effective_from": {"source": "Effective Date", "type": "date"},
                    "classification_code": {"source": "AuditHero Classification Code"},
                },
            },
            "employment_history": {
                "enabled": True,
                "source": {"file": "employment_history.csv"},
                "columns": {
                    "employee_id": {"source": "Employee Number"},
                    "start_date": {"source": "Start Date", "type": "date"},
                    "employment_type": {"source": "Employment Type", "value_map": {"Casual": "CASUAL"}},
                },
            },
            "timesheets": {
                "enabled": True,
                "source": {"file": "timesheets.csv"},
                "columns": {
                    "timesheet_id": {"source": "Entry ID"},
                    "employee_id": {"source": "Employee Number"},
                    "start_datetime": {"date_source": "Shift Date", "time_source": "Start Time", "type": "datetime"},
                    "end_datetime": {"date_source": "Shift Date", "time_source": "End Time", "type": "datetime"},
                },
            },
        },
    }
    output = tmp_path / "canonical"
    result = convert_source_files(tmp_path, mapping, output)
    assert not result["errors"]
    assert (output / "audithero_input.xlsx").exists()
    assert (output / "conversion_report.csv").exists()
    employees = pd.read_csv(output / "employees.csv")
    assert employees.loc[0, "employee_name"] == "Ada Example"
    assert employees.loc[0, "employment_type_current"] == "CASUAL"


def test_mapping_rejects_source_outside_root(tmp_path: Path):
    outside = tmp_path.parent / "outside.csv"
    pd.DataFrame([{"x": 1}]).to_csv(outside, index=False)
    mapping = {
        "version": 1,
        "datasets": {
            "employees": {
                "enabled": True,
                "source": {"file": str(outside)},
                "columns": {"employee_id": {"source": "x"}, "employee_name": {"source": "x"}},
            }
        },
    }
    result = convert_source_files(tmp_path, mapping, tmp_path / "out", strict=False)
    assert result["errors"]
