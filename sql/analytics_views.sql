CREATE OR REPLACE VIEW schads_payroll.gold.v_exception_periods AS
SELECT * FROM schads_payroll.gold.v_reconciliation_latest
WHERE status IN ('UNDERPAID','OVERPAID','REQUIRES_REVIEW','ACTUAL_PAY_UNAVAILABLE');

CREATE OR REPLACE VIEW schads_payroll.gold.v_employee_month AS
SELECT date_trunc('MONTH',shift_start) month,employee_id,employee_name,
       sum(expected_amount) expected_amount,count(*) shifts,
       sum(CASE WHEN entitlement_status='REQUIRES_REVIEW' THEN 1 ELSE 0 END) review_shifts
FROM schads_payroll.gold.v_audit_detail_latest
GROUP BY ALL;
