# Databricks notebook source
exec(open(str(Path.cwd()/'_common.py')).read());from schads_audit.rules import RuleLibrary;import pandas as pd
dbutils.widgets.text('classification_code','SACS-L2-P3');code=dbutils.widgets.get('classification_code');lib=RuleLibrary(ROOT/'rules/MA000100');rows=[]
for p in lib.rate_packs:
 r,_=lib.rate(code,p['operative_date']);rows.append({'operative_date':p['operative_date'],'classification_code':code,'base_hourly_rate':r['base_hourly_rate'] if r else None,'source':p['source'].get('title')})
display(pd.DataFrame(rows))
