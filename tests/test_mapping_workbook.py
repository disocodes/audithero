from pathlib import Path
import pandas as pd

from schads_audit.mapping_workbook import write_mapping_workbook, load_mapping_workbook


def test_mapping_workbook_round_trip(tmp_path: Path):
    draft = {
        "version": 1,
        "datasets": {
            "employees": {
                "enabled": True,
                "source": {"file": "employees.csv", "sheet": None, "header": 0},
                "columns": {
                    "employee_id": {"source": "Employee Number"},
                    "employee_name": {"source": "Full Name"},
                },
                "_suggestions": {
                    "employee_id": {"suggested_source": "Employee Number", "confidence": 1.0},
                    "employee_name": {"suggested_source": "Full Name", "confidence": 1.0},
                },
            }
        },
    }
    path = tmp_path / "source_mapping.xlsx"
    write_mapping_workbook(draft, path)
    assert path.exists()

    # Add a value translation exactly as an operator would in Excel.
    fields = pd.read_excel(path, sheet_name="field_mapping")
    values = pd.DataFrame([
        {"dataset": "employees", "target_field": "employment_type_current", "source_value": "Permanent FT", "target_value": "FULL_TIME", "notes": ""}
    ])
    readme = pd.read_excel(path, sheet_name="README", header=None)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        readme.to_excel(writer, sheet_name="README", header=False, index=False)
        fields.to_excel(writer, sheet_name="field_mapping", index=False)
        values.to_excel(writer, sheet_name="value_mapping", index=False)

    mapping = load_mapping_workbook(path)
    assert mapping["version"] == 1
    assert mapping["datasets"]["employees"]["enabled"] is True
    assert mapping["datasets"]["employees"]["columns"]["employee_id"]["source"] == "Employee Number"
