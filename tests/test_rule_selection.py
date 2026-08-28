from pathlib import Path
from schads_audit.rules import RuleLibrary
ROOT=Path(__file__).resolve().parents[1]
def lib():return RuleLibrary(ROOT/'rules/MA000100')
def test_library_valid():assert lib().validate()==[]
def test_2024_rate():
 r,p=lib().rate('SACS-L2-P3','2024-09-15');assert r['base_hourly_rate']==35.51 and p['operative_date']=='2024-07-01'
def test_2026_rate():assert lib().rate('SACS-L2-P3','2026-08-01')[0]['base_hourly_rate']==38.50
def test_sleepover_change_boundary():assert lib().conditions('2026-05-31')['sleepover']['surrounding_work_is_one_shift'] is False and lib().conditions('2026-06-01')['sleepover']['surrounding_work_is_one_shift'] is True
