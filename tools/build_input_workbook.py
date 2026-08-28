#!/usr/bin/env python3
"""Create a self-contained AuditHero Excel workbook for manual imports."""
from pathlib import Path
import argparse
import pandas as pd

SHEETS={
 "employees":["employee_id","employee_name","employment_type_current","state","work_group"],
 "pay_details":["employee_id","effective_from","classification_code","classification_name","industrial_instrument"],
 "employment_history":["employee_id","start_date","end_date","employment_type","contract_type","title"],
 "timesheets":["timesheet_id","employee_id","start_datetime","end_datetime","unpaid_break_minutes","work_group","location_state","holiday_location_key","work_type_name","is_sleepover","sleepover_active_minutes","sleepover_12h_written_agreement","pay_period_start","pay_period_end"],
 "rostered_shifts":["rostered_shift_id","employee_id","rostered_start_datetime","rostered_end_datetime","rostered_break_minutes","work_type_name","work_site_id"],
 "payroll_earnings":["payroll_line_id","pay_run_id","employee_id","timesheet_id","pay_period_start","pay_period_end","earning_date","pay_category_id","pay_category","hours","rate","amount"],
 "pay_runs":["pay_run_id","pay_period_start","pay_period_end","status"],
 "pay_category_mapping":["pay_category_id","pay_category","audit_treatment"],
 "industrial_instrument_history":["employee_id","effective_from","effective_to","instrument_type","instrument_name","award_code","document_reference"],
 "part_time_patterns":["employee_id","effective_from","effective_to","weekday","start_time","end_time","guaranteed_hours","agreement_reference"],
 "part_time_variations":["employee_id","shift_date","start_time","end_time","agreement_reference"],
 "public_holiday_overrides":["state","holiday_date","holiday_name","holiday_location_key","holiday_scope","source"],
 "overtime_rest_controls":["employee_id","timesheet_id","shift_start","employer_instructed_resume","evidence_reference"],
 "meal_break_events":["event_id","employee_id","timesheet_id","mode","scheduled_break_start","actual_break_start","deducted_break_minutes","paid_meal_minutes","evidence_reference"],
 "supplemental_events":["event_id","employee_id","event_type","start_datetime","end_datetime","pay_period_start","pay_period_end","employment_type","classification_code","higher_classification_code","work_group","state","hours","on_call","training_or_meeting","unpaid_breaks","two_breaks_agreed","span_hours","period_minimums_verified","shift_hours","consecutive_working_days"],
 "toil_register":["agreement_id","employee_id","overtime_datetime","overtime_hours","written_agreement","agreement_date","time_off_hours","time_off_date","payment_requested_date","payment_date","payment_pay_period_start","payment_pay_period_end","employment_end_date","classification_code","employment_type","work_group","state","holiday_location_key","evidence_reference"],
}

README=[
 ["AuditHero manual payroll-audit workbook"],
 ["API credentials","Not required. This workbook can be the complete data/evidence source."],
 ["Required sheets","employees, pay_details, employment_history, timesheets"],
 ["Recommended","rostered_shifts for full-time overtime; pay_runs for reliable Award version selection"],
 ["Actual payroll","payroll_earnings + pay_category_mapping enable under/over-payment reconciliation"],
 ["Historical coverage","industrial_instrument_history is a key remediation control"],
 ["Part-time","part_time_patterns is required where part-time employment exists"],
 ["Optional controls","holiday overrides, meal/rest events, supplemental events and TOIL may be blank if not applicable"],
 ["Dates","Use ISO YYYY-MM-DD; datetimes YYYY-MM-DD HH:MM:SS where possible"],
 ["Classification","classification_code must use a loaded canonical code such as SACS-L2-P3"],
 ["Pay category treatment","Use AUDITABLE_WORK, ALLOWANCE or EXCLUDE"],
 ["Fabric location","Lakehouse Files/input/audithero_input.xlsx"],
 ["Databricks location","/Volumes/<catalog>/bronze/landing/input/audithero_input.xlsx"],
]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",default="audithero_input.xlsx"); args=ap.parse_args()
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        pd.DataFrame(README).to_excel(writer,sheet_name="README",header=False,index=False)
        for name,cols in SHEETS.items(): pd.DataFrame(columns=cols).to_excel(writer,sheet_name=name,index=False)
    print(out.resolve())

if __name__=="__main__": main()
