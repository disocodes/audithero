import time,requests
class EmploymentHeroPayrollClient:
    def __init__(self,api_key,business_id,base_url='https://api.yourpayroll.com.au/api/v2',timeout=60,min_interval=.22):self.api_key=api_key;self.business_id=str(business_id);self.base_url=base_url.rstrip('/');self.timeout=timeout;self.min_interval=min_interval;self._last=0.0
    def _get(self,path,params=None):
        for attempt in range(6):
            gap=time.monotonic()-self._last
            if gap<self.min_interval:time.sleep(self.min_interval-gap)
            r=requests.get(f"{self.base_url}/{path.lstrip('/')}",params=params or {},auth=(self.api_key,''),headers={'Accept':'application/json'},timeout=self.timeout);self._last=time.monotonic()
            if r.status_code==429:time.sleep(min(2**attempt,30));continue
            r.raise_for_status();return r.json()
        raise RuntimeError(f'Payroll API request failed: {path}')
    @staticmethod
    def _array(p):
        if isinstance(p,list):return p
        if isinstance(p,dict):
            for k in ('items','data','results','payRuns','payruns','earningsLines','earningslines'):
                if isinstance(p.get(k),list):return p[k]
        return []
    @staticmethod
    def _first(r,*keys):
        for k in keys:
            if isinstance(r,dict) and r.get(k) not in (None,''):return r[k]
    def list_pay_runs(self):return self._array(self._get(f'business/{self.business_id}/payrun'))
    def pay_runs_overlapping(self,start,end):
        s=str(start)[:10];e=str(end)[:10];out=[]
        for r in self.list_pay_runs():
            ps=str(self._first(r,'payPeriodStarting','PayPeriodStarting','payPeriodStart','startDate') or '')[:10];pe=str(self._first(r,'payPeriodEnding','PayPeriodEnding','payPeriodEnd','endDate') or '')[:10]
            if ps and pe and not(pe<s or ps>e):out.append(r)
        return out
    def earnings_lines(self,rid):return self._array(self._get(f'business/{self.business_id}/payrun/{rid}/earningslines'))
    def pull_earnings(self,start,end):
        runs=self.pay_runs_overlapping(start,end);rows=[]
        for run in runs:
            rid=self._first(run,'id','Id','payRunId','PayRunId')
            if rid is None:continue
            for line in self.earnings_lines(rid):
                x=dict(line);x['_pay_run_id']=rid;x['_pay_period_start']=self._first(run,'payPeriodStarting','PayPeriodStarting','payPeriodStart','startDate');x['_pay_period_end']=self._first(run,'payPeriodEnding','PayPeriodEnding','payPeriodEnd','endDate');x['_pay_run_status']=self._first(run,'status','Status');rows.append(x)
        return runs,rows
