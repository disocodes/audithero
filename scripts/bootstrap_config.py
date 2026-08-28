#!/usr/bin/env python3
"""Create safe active AuditHero tenant config files from example schemas.

JSON mappings are initialized to empty objects. CSV registers inherit only the header
from their example files, never sample rows. Existing active files are never changed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"

JSON_FILES = [
    "classification_mapping.json",
    "work_type_mapping.json",
    "work_location_state_mapping.json",
    "employee_overrides.json",
    "pay_category_mapping.json",
]

CSV_FILES = [
    "public_holiday_overrides.csv",
    "industrial_instrument_history.csv",
    "part_time_patterns.csv",
    "part_time_variations.csv",
    "overtime_rest_controls.csv",
    "meal_break_events.csv",
    "supplemental_events.csv",
    "toil_register.csv",
]


def example_path(active_name: str) -> Path:
    stem, suffix = active_name.rsplit(".", 1)
    return CONFIG / f"{stem}.example.{suffix}"


def main() -> int:
    created=[]; existing=[]
    CONFIG.mkdir(parents=True,exist_ok=True)

    for name in JSON_FILES:
        target=CONFIG/name
        if target.exists():
            existing.append(name); continue
        target.write_text("{}\n",encoding="utf-8")
        created.append(name)

    for name in CSV_FILES:
        target=CONFIG/name
        if target.exists():
            existing.append(name); continue
        example=example_path(name)
        if not example.exists():
            raise FileNotFoundError(f"Missing example schema for {name}: {example}")
        lines=example.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].strip():
            raise ValueError(f"Example register has no CSV header: {example}")
        target.write_text(lines[0].rstrip()+"\n",encoding="utf-8")
        created.append(name)

    print("AuditHero tenant config bootstrap")
    if created:
        print("Created safe empty active files:")
        for name in created: print(f"  + config/{name}")
    if existing:
        print("Preserved existing active files:")
        for name in existing: print(f"  = config/{name}")
    print("No example/sample data was copied into active control registers.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
