from pathlib import Path
from datetime import date, datetime
import json

from .dates import as_date


def _rule_date(value):
    """Parse machine-controlled rule-pack dates with the cheap ISO path.

    Rule manifests are repository-controlled ISO dates, not operator-entered dates,
    so they should never go through the general pandas/Australian parser on every
    rule lookup.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    return date.fromisoformat(text[:10])


class RuleLibrary:
    def __init__(self,root):
        self.root=Path(root);self.manifest=self._read('manifest.json')
        self.rate_packs=[self._read(x) for x in self.manifest['rates']]
        self.condition_packs=[self._read(x) for x in self.manifest['conditions']]
        self.allowance_packs=[self._read(x) for x in self.manifest['allowances']]

        # Rule pack dates are immutable machine data. Parse them once and cache all
        # frequently repeated date/classification lookups used by scenario passes.
        for pack in self.rate_packs + self.condition_packs + self.allowance_packs:
            pack['_operative_date_obj']=_rule_date(pack['operative_date'])

        self._select_cache={}
        self._rate_cache={}
        self._allowance_cache={}

    def _read(self,rel):return json.loads((self.root/rel).read_text(encoding='utf-8'))

    @staticmethod
    def _select_uncached(packs,ref):
        eligible=[p for p in packs if p['_operative_date_obj']<=ref]
        return max(eligible,key=lambda p:p['_operative_date_obj']) if eligible else None

    def _select(self,label,packs,ref_date):
        d=as_date(ref_date)
        key=(label,d)
        if key not in self._select_cache:
            self._select_cache[key]=self._select_uncached(packs,d)
        return self._select_cache[key]

    def rates(self,d):return self._select('rates',self.rate_packs,d)
    def conditions(self,d):return self._select('conditions',self.condition_packs,d)
    def allowances(self,d):return self._select('allowances',self.allowance_packs,d)

    def rate(self,code,d):
        """Select the latest eligible pack which actually contains the classification code."""
        if not code:return None,None
        ref=as_date(d)
        cache_key=(str(code),ref)
        if cache_key in self._rate_cache:
            return self._rate_cache[cache_key]

        candidates=[]
        for p in self.rate_packs:
            if p['_operative_date_obj']>ref:continue
            row=next((r for r in p['rates'] if r['classification_code']==code),None)
            if row:candidates.append((p['_operative_date_obj'],p,row))
        if not candidates:
            result=(None,None)
        else:
            _,pack,row=max(candidates,key=lambda x:x[0]);result=(row,pack)
        self._rate_cache[cache_key]=result
        return result

    def allowance(self,key,d):
        ref=as_date(d)
        cache_key=(str(key),ref)
        if cache_key in self._allowance_cache:
            return self._allowance_cache[cache_key]
        p=self.allowances(ref)
        if not p:
            result=(None,None)
        else:
            result=(next((r for r in p['allowances'] if r['key']==key),None),p)
        self._allowance_cache[cache_key]=result
        return result

    def validate(self):
        errors=[]
        for label,packs in [('conditions',self.condition_packs),('allowances',self.allowance_packs)]:
            dates=[p['_operative_date_obj'] for p in packs]
            if dates!=sorted(dates):errors.append(f'{label}: manifest entries are not chronological')
            if len(dates)!=len(set(dates)):errors.append(f'{label}: duplicate operative_date')
        seen=set();last_by_family={}
        for p in self.rate_packs:
            family=p.get('classification_family','UNSPECIFIED');d=p['_operative_date_obj']
            if family in last_by_family and d<last_by_family[family]:errors.append(f'rates: {family} packs are not chronological')
            last_by_family[family]=d
            codes=[r['classification_code'] for r in p['rates']]
            if len(codes)!=len(set(codes)):errors.append(f"{p['rate_pack_id']}: duplicate classification")
            for code in codes:
                item=(d,code)
                if item in seen:errors.append(f'rates: duplicate {code} on {d}')
                seen.add(item)
            if any(float(r['base_hourly_rate'])<=0 for r in p['rates']):errors.append(f"{p['rate_pack_id']}: invalid rate")
        return errors

    def coverage_rows(self):
        out=[]
        for typ,packs,key in [('RATE',self.rate_packs,'rate_pack_id'),('CONDITION',self.condition_packs,'condition_pack_id'),('ALLOWANCE',self.allowance_packs,'allowance_pack_id')]:
            for p in packs:
                out.append({'pack_type':typ,'pack_id':p[key],'operative_date':p['operative_date'],'classification_family':p.get('classification_family'),'source_publisher':p.get('source',{}).get('publisher'),'source_url':p.get('source',{}).get('url'),'verification_status':p.get('source',{}).get('verification_status')})
        return out
