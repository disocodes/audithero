from pathlib import Path
import pandas as pd

from schads_audit.file_source import load_file_source, input_inventory
from schads_audit.manual_audit import _assign_manual_pay_periods


def _frames():
    return {
        "employees":pd.DataFrame([{"employee_id":"E1","employee_name":"Test"}]),
        "pay_details":pd.DataFrame([{"employee_id":"E1","effective_from":"2023-07-01","classification_code":"SACS-L2-P3"}]),
        "employment_history":pd.DataFrame([{"employee_id":"E1","start_date":"2023-01-01","employment_type":"CASUAL"}]),
        "timesheets":pd.DataFrame([{"timesheet_id":"T1","employee_id":"E1","start_datetime":"2026-08-08 09:00","end_datetime":"2026-08-08 13:00"}]),
    }


def test_single_workbook_load(tmp_path):
    p=tmp_path/"audithero_input.xlsx"
    with pd.ExcelWriter(p,engine="openpyxl") as writer:
        for name,df in _frames().items(): df.to_excel(writer,sheet_name=name,index=False)
    loaded=load_file_source(tmp_path,"2026-08-01","2026-08-31")
    assert len(loaded["employees"])==1
    assert len(loaded["timesheets"])==1
    assert loaded["payroll_earnings"].empty
    inv=input_inventory(tmp_path)
    assert bool(inv.loc[inv.dataset=="employees","found"].iloc[0])


def test_separate_csv_load(tmp_path):
    for name,df in _frames().items(): df.to_csv(tmp_path/f"{name}.csv",index=False)
    loaded=load_file_source(tmp_path)
    assert loaded["pay_details"].iloc[0]["classification_code"]=="SACS-L2-P3"


def test_manual_pay_run_assigns_period():
    ts=_frames()["timesheets"]
    runs=pd.DataFrame([{"pay_run_id":"P1","pay_period_start":"2026-08-03","pay_period_end":"2026-08-16","status":"FINAL"}])
    out=_assign_manual_pay_periods(ts,runs)
    assert str(out.iloc[0]["pay_period_start"])[:10]=="2026-08-03"
    assert out.iloc[0]["pay_run_id"]=="P1"


def test_overlapping_pay_runs_do_not_guess():
    ts=_frames()["timesheets"]
    runs=pd.DataFrame([
        {"pay_run_id":"P1","pay_period_start":"2026-08-03","pay_period_end":"2026-08-16"},
        {"pay_run_id":"P2","pay_period_start":"2026-08-01","pay_period_end":"2026-08-14"},
    ])
    out=_assign_manual_pay_periods(ts,runs)
    assert pd.isna(out.iloc[0]["pay_period_start"]) or out.iloc[0]["pay_period_start"] in (None,"")
