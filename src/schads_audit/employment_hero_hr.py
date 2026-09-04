from __future__ import annotations
import time,requests
from .dates import as_date, iso_date, month_chunks


class EmploymentHeroHRClient:
    def __init__(self,client_id,client_secret,refresh_token,base_url='https://api.employmenthero.com/api/v1',token_url='https://oauth.employmenthero.com/oauth2/token',timeout=60,min_interval=.62):
        self.client_id=client_id;self.client_secret=client_secret;self.refresh_token=refresh_token;self.base_url=base_url.rstrip('/');self.token_url=token_url;self.timeout=timeout;self.min_interval=min_interval;self._access_token=None;self._last_request=0.0
    def _throttle(self):
        d=time.monotonic()-self._last_request
        if d<self.min_interval:time.sleep(self.min_interval-d)
    def refresh_access_token(self):
        r=requests.post(self.token_url,params={'grant_type':'refresh_token','refresh_token':self.refresh_token},data={'client_id':self.client_id,'client_secret':self.client_secret},headers={'Content-Type':'application/x-www-form-urlencoded'},timeout=self.timeout);r.raise_for_status();b=r.json();self._access_token=b['access_token'];return b
    def headers(self):
        if not self._access_token:self.refresh_access_token()
        return {'Authorization':f'Bearer {self._access_token}','Accept':'application/json'}
    def _get(self,path,params=None):
        for attempt in range(6):
            self._throttle();r=requests.get(f"{self.base_url}/{path.lstrip('/')}",headers=self.headers(),params=params or {},timeout=self.timeout);self._last_request=time.monotonic()
            if r.status_code==401 and attempt==0:self._access_token=None;continue
            if r.status_code==429:time.sleep(min(2**attempt,60));continue
            r.raise_for_status();return r.json()
        raise RuntimeError(f'Employment Hero request failed: {path}')
    @staticmethod
    def _items(payload):
        data=payload.get('data',payload) if isinstance(payload,dict) else payload
        if isinstance(data,dict) and 'items' in data:return data['items'],data
        if isinstance(data,list):return data,{}
        return ([data] if data else []),{}
    def paged(self,path,params=None):
        page=1;out=[]
        while True:
            q=dict(params or {});q.update({'page_index':page,'item_per_page':100});payload=self._get(path,q);items,meta=self._items(payload);out.extend(items);total=int(meta.get('total_pages',page))
            if page>=total or not items:break
            page+=1
        return out
    def organisations(self):return self.paged('organisations')
    def employees(self,org):return self.paged(f'organisations/{org}/employees')
    def pay_details(self,org,eid):return self.paged(f'organisations/{org}/employees/{eid}/pay_details')
    def employment_histories(self,org,eid):return self.paged(f'organisations/{org}/employees/{eid}/employment_histories')
    def all_employee_histories(self,org,eids):
        pay=[];employment=[]
        for eid in eids:
            for r in self.pay_details(org,eid):x=dict(r);x.setdefault('employee_id',eid);pay.append(x)
            for r in self.employment_histories(org,eid):x=dict(r);x.setdefault('employee_id',eid);employment.append(x)
        return pay,employment
    def timesheets(self,org,start,end,employee_id='-'):
        au=lambda d:as_date(d).strftime('%d/%m/%Y')
        return self.paged(f'organisations/{org}/employees/{employee_id}/timesheet_entries',{'start_date':au(start),'end_date':au(end)})
    def timesheets_chunked(self,org,start,end):
        out=[]
        for s,e in month_chunks(start,end):out.extend(self.timesheets(org,s,e,'-'))
        return out
    def rostered_shifts(self,org,start,end):
        return self.paged(f'organisations/{org}/rostered_shifts',{'from_date':iso_date(start),'to_date':iso_date(end),'exclude_shifts_overlapping_from_date':'false'})
    def rostered_shifts_chunked(self,org,start,end):
        out=[]
        for s,e in month_chunks(start,end):out.extend(self.rostered_shifts(org,s,e))
        return out
    def awards_and_classifications(self,org):return self.paged(f'organisations/{org}/awards_and_classifications')
    def pay_categories(self,org):return self.paged(f'organisations/{org}/pay_categories')
    def work_types(self,org):return self.paged(f'organisations/{org}/work_types')
    def work_locations(self,org):return self.paged(f'organisations/{org}/work_locations')
