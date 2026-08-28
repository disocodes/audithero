from pathlib import Path
from datetime import date,datetime
import json

def as_date(v):
    if isinstance(v,datetime):return v.date()
    if isinstance(v,date):return v
    return datetime.fromisoformat(str(v)[:10]).date()

class RuleLibrary:
    def __init__(self,root):
        self.root=Path(root);self.manifest=self._read('manifest.json')
        self.rate_packs=[self._read(x) for x in self.manifest['rates']]
        self.condition_packs=[self._read(x) for x in self.manifest['conditions']]
        self.allowance_packs=[self._read(x) for x in self.manifest['allowances']]
    def _read(self,rel):return json.loads((self.root/rel).read_text(encoding='utf-8'))
    @staticmethod
    def _select(packs,ref_date):
        d=as_date(ref_date);eligible=[p for p in packs if as_date(p['operative_date'])<=d]
        return max(eligible,key=lambda p:as_date(p['operative_date'])) if eligible else None
    def rates(self,d):return self._select(self.rate_packs,d)
    def conditions(self,d):return self._select(self.condition_packs,d)
    def allowances(self,d):return self._select(self.allowance_packs,d)
    def rate(self,code,d):
        p=self.rates(d)
        if not p:return None,None
        return next((r for r in p['rates'] if r['classification_code']==code),None),p
    def allowance(self,key,d):
        p=self.allowances(d)
        if not p:return None,None
        return next((r for r in p['allowances'] if r['key']==key),None),p
    def validate(self):
        errors=[]
        for label,packs in [('rates',self.rate_packs),('conditions',self.condition_packs),('allowances',self.allowance_packs)]:
            dates=[as_date(p['operative_date']) for p in packs]
            if dates!=sorted(dates):errors.append(f'{label}: manifest entries are not chronological')
            if len(dates)!=len(set(dates)):errors.append(f'{label}: duplicate operative_date')
        for p in self.rate_packs:
            codes=[r['classification_code'] for r in p['rates']]
            if len(codes)!=len(set(codes)):errors.append(f"{p['rate_pack_id']}: duplicate classification")
            if any(float(r['base_hourly_rate'])<=0 for r in p['rates']):errors.append(f"{p['rate_pack_id']}: invalid rate")
        return errors
    def coverage_rows(self):
        out=[]
        for typ,packs,key in [('RATE',self.rate_packs,'rate_pack_id'),('CONDITION',self.condition_packs,'condition_pack_id'),('ALLOWANCE',self.allowance_packs,'allowance_pack_id')]:
            for p in packs:
                out.append({'pack_type':typ,'pack_id':p[key],'operative_date':p['operative_date'],'source_publisher':p.get('source',{}).get('publisher'),'source_url':p.get('source',{}).get('url'),'verification_status':p.get('source',{}).get('verification_status')})
        return out
