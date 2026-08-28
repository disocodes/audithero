# Databricks notebook source
exec(open(str(Path.cwd()/'_common.py')).read());from schads_audit.rules import RuleLibrary;import pandas as pd
lib=RuleLibrary(ROOT/'rules/MA000100');errors=lib.validate()
if errors:raise ValueError('\n'.join(errors))
display(pd.DataFrame(lib.coverage_rows()).sort_values(['pack_type','operative_date']))
