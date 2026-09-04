import json,re,pandas as pd

from .dates import parse_datetime_value


def first(x,*keys,default=None):
    for k in keys:
        if isinstance(x,dict) and x.get(k) not in (None,''):return x[k]
    return default

def raw_json(x):return json.dumps(x,default=str,separators=(',',':'))

def _break_minutes(breaks):
    total=0.0
    for b in breaks or []:
        s=parse_datetime_value(first(b,'start_time','startTime','start'));e=parse_datetime_value(first(b,'end_time','endTime','end'))
        if not pd.isna(s) and not pd.isna(e) and e>s:total+=(e-s).total_seconds()/60
    return round(total,2)

def normalize_employees(items):return pd.DataFrame([{'employee_id':first(x,'id','employee_id','employeeId','Id'),'employee_name':first(x,'full_name','fullName','display_name','displayName','name'),'employment_type_current':first(x,'employment_type','employmentType'),'state':first(x,'state','location_state','locationState'),'raw_json':raw_json(x)} for x in items])
def normalize_pay_details(items):return pd.DataFrame([{'employee_id':first(x,'employee_id','employeeId'),'effective_from':first(x,'effective_from','effectiveFrom'),'classification_name':first(x,'classification','classification_name','classificationName'),'industrial_instrument':first(x,'industrial_instrument','industrialInstrument'),'pay_detail_id':first(x,'id','Id'),'raw_json':raw_json(x)} for x in items])
def normalize_employment_history(items):return pd.DataFrame([{'employee_id':first(x,'employee_id','employeeId'),'employment_history_id':first(x,'id','Id'),'start_date':first(x,'start_date','startDate'),'end_date':first(x,'end_date','endDate'),'employment_type':first(x,'employment_type','employmentType'),'contract_type':first(x,'contract_type','contractType'),'title':first(x,'title'),'raw_json':raw_json(x)} for x in items])

def normalize_timesheets(items):
    rows=[]
    for x in items:
        d=first(x,'date');s=first(x,'start_time','startTime','start_datetime','startDateTime','start');e=first(x,'end_time','endTime','end_datetime','endDateTime','end')
        if d and s and 'T' not in str(s):s=f'{d}T{s}'
        if d and e and 'T' not in str(e):e=f'{d}T{e}'
        breaks=first(x,'breaks',default=[]) or [];mins=_break_minutes(breaks);bu=first(x,'break_units','breakUnits')
        if mins and bu in (None,''):bu=mins/60
        rows.append({'timesheet_id':first(x,'id','timesheet_entry_id','timesheetEntryId','Id'),'employee_id':first(x,'employee_id','employeeId','member_id','memberId'),'start_datetime':s,'end_datetime':e,'units':first(x,'units','hours','total_hours','totalHours'),'break_units':bu,'unpaid_break_minutes':mins or None,'rostered_shift_id':first(x,'rostered_shift_id','rosteredShiftId'),'work_type_id':first(x,'work_type_id','workTypeId'),'work_type_name':first(x,'work_type','workType','work_type_name','workTypeName'),'work_site_id':first(x,'work_site_id','workSiteId'),'location_id':first(x,'location_id','locationId'),'position_name':first(x,'position_name','positionName'),'comment':first(x,'comment','notes','description'),'status':first(x,'status'),'raw_json':raw_json(x)})
    return pd.DataFrame(rows)

def normalize_payroll_earnings(items):return pd.DataFrame([{'payroll_line_id':first(x,'id','Id','earningsLineId','EarningsLineId'),'pay_run_id':first(x,'_pay_run_id','payRunId','PayRunId'),'pay_run_status':first(x,'_pay_run_status','status','Status'),'employee_id':first(x,'employeeId','EmployeeId','employee_id'),'timesheet_id':first(x,'timesheetId','TimesheetId','timesheet_id'),'pay_period_start':first(x,'_pay_period_start','payPeriodStarting','PayPeriodStarting'),'pay_period_end':first(x,'_pay_period_end','payPeriodEnding','PayPeriodEnding'),'earning_date':first(x,'date','Date','earningDate','EarningDate'),'pay_category_id':first(x,'payCategoryId','PayCategoryId'),'pay_category':first(x,'payCategoryName','PayCategoryName','payCategory','PayCategory'),'hours':first(x,'hours','Hours','units','Units'),'rate':first(x,'rate','Rate','payRate','PayRate'),'amount':first(x,'amount','Amount','earnings','Earnings'),'raw_json':raw_json(x)} for x in items])

def infer_schads_classification(name):
    """Infer only when the source text explicitly identifies a supported SCHADS stream, level and pay point."""
    s=str(name or '')
    if re.search(r'home\s*care',s,re.I) and re.search(r'disability',s,re.I):
        m=re.search(r'level\s*(\d+).*?pay\s*point\s*(\d+)',s,re.I)
        if m:return f'HC-DIS-L{int(m.group(1))}-P{int(m.group(2))}'
    if not re.search(r'social\s*(?:and|&)\s*community',s,re.I):return None
    m=re.search(r'level\s*(\d+).*?pay\s*point\s*(\d+)',s,re.I);return f'SACS-L{int(m.group(1))}-P{int(m.group(2))}' if m else None

def apply_classification_mapping(df,mapping):
    out=df.copy()
    if out.empty:out['classification_code']=None;return out
    out['classification_code']=out.apply(lambda r:next((mapping[k].get('classification_code') if isinstance(mapping[k],dict) else mapping[k] for k in [str(r.get('pay_detail_id') or ''),str(r.get('classification_name') or '')] if k in mapping),infer_schads_classification(r.get('classification_name'))),axis=1);return out

def apply_employee_overrides(df,overrides):
    """Apply explicit employee overrides without inventing an Award work group.

    Missing work-group evidence remains blank. The entitlement engine converts a
    blank work group to OTHER and marks the affected calculation for review.
    """
    out=df.copy()
    if 'work_group' not in out.columns:out['work_group']=None
    for i,r in out.iterrows():
        for k,v in overrides.get(str(r['employee_id']),{}).items():out.at[i,k]=v
    return out
