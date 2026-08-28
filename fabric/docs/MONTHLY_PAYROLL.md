# Monthly payroll workflow on Fabric

The monthly schedule is deployed **disabled** until a validation sample is accepted.

Default operational model:

1. Managers approve timesheets.
2. Payroll prepares the draft pay run.
3. Fabric monthly pipeline runs a recent lookback window.
4. AuditHero recalculates SCHADS entitlements and reconciles actual earnings.
5. `gold.current_*` snapshots are refreshed.
6. Direct Lake/Power BI reflects the latest successful audit.
7. Payroll reviews instrument issues, review items, underpayments and overpayments.
8. Payroll corrects source payroll as appropriate.
9. Re-run before finalisation when practical.

The default lookback is configurable (recommended 45 days) to tolerate weekly/fortnightly/monthly cycles. Pay-period boundaries from Employment Hero Payroll are used where available.

Do not automatically deduct an overpayment from wages. Handle overpayment recovery through the employer's lawful process.