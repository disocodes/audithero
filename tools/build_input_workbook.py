#!/usr/bin/env python3
"""Create a blank AuditHero Excel workbook for manual imports."""
from pathlib import Path
import argparse
import pandas as pd

SHEETS = {
    "employees": [
        "employee_id","employee_name","employment_type_current","state","work_group"
    ],
    "pay_details": [
        "employee_id","effective_from","classification_code","classification_name","industrial_instrument"
    ],
    "employment_history": [
        "employee_id","start_date","end_date","employment_type","contract_type","title"
    ],
    "timesheets": [
        "timesheet_id","employee_id","start_datetime","end_datetime","unpaid_break_minutes",
        "work_group","location_state","holiday_location_key","work_type_name","is_sleepover",
        "sleepover_active_minutes","sleepover_12h_written_agreement","pay_period_start","pay_period_end"
    ],
    "rostered_shifts": [
        "rostered_shift_id","employee_id","rostered_start_datetime","rostered_end_datetime",
        "rostered_break_minutes","work_type_name","work_site_id"
    ],
    "payroll_earnings": [
        "payroll_line_id","pay_run_id","employee_id","timesheet_id","pay_period_start","pay_period_end",
        "earning_date","pay_category_id","pay_category","hours","rate","amount"
    ],
    "pay_runs": [
        "pay_run_id","pay_period_start","pay_period_end","status"
    ],
}

README = [
    ["AuditHero manual payroll-audit workbook"],
    ["Required sheets", "employees, pay_details, employment_history, timesheets"],
    ["Recommended", "rostered_shifts for full-time overtime analysis"],
    ["Optional", "payroll_earnings/pay_runs for actual-vs-expected reconciliation"],
    ["Dates", "Use ISO YYYY-MM-DD; datetimes YYYY-MM-DD HH:MM:SS where possible"],
    ["Classification", "classification_code must use a loaded canonical code such as SACS-L2-P3"],
    ["Employment types", "FULL_TIME, PART_TIME or CASUAL (common spelling variants are accepted)"],
    ["Input location", "Fabric: Lakehouse Files/input/audithero_input.xlsx; Databricks: configured input_root"],
]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="audithero_input.xlsx")
    args=ap.parse_args()
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        pd.DataFrame(README).to_excel(writer,sheet_name="README",header=False,index=False)
        for name,cols in SHEETS.items():
            pd.DataFrame(columns=cols).to_excel(writer,sheet_name=name,index=False)
    print(out.resolve())

if __name__ == "__main__":
    main()
