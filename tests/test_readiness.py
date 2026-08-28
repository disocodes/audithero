import pandas as pd

from schads_audit.readiness import employee_register_coverage, coverage_detail


def test_instrument_register_requires_every_employee():
    register=pd.DataFrame([
        {'employee_id':'E1','effective_from':'2023-07-01','instrument_type':'AWARD'},
        {'employee_id':'sample-employee','effective_from':'2023-07-01','instrument_type':'AWARD'},
    ])
    result=employee_register_coverage(register,['E1','E2'])
    assert result['covered'] is False
    assert result['missing']=={'E2'}
    assert 'E2' in coverage_detail(result,'industrial-instrument history')


def test_register_coverage_ignores_example_rows_not_in_population():
    register=pd.DataFrame([{'employee_id':'employee-uuid'}])
    result=employee_register_coverage(register,['REAL-1'])
    assert result['covered'] is False
    assert result['present']=={'employee-uuid'}
    assert result['missing']=={'REAL-1'}


def test_empty_required_population_is_covered():
    result=employee_register_coverage(pd.DataFrame(),[])
    assert result['covered'] is True
    assert result['missing']==set()
