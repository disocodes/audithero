# Databricks AI/BI dashboard

The bundle includes `AuditHero - SCHADS Payroll Compliance`, removing the Power BI dependency.

Recommended user flow:

- **Payroll Overview** — monthly status and volume.
- **Exceptions** — employee/pay-period underpayment, overpayment and review queue.
- **Shift Evidence** — expected amount and calculation evidence by shift.
- **Rule Library** — rule-pack dates and source evidence.

The dashboard datasets use `gold.v_reconciliation_latest`, `gold.v_audit_detail_latest` and `ref.rule_coverage`.

Set the SQL warehouse before deployment:

```bash
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
```

Grant payroll consumers only the Unity Catalog privileges needed to query Gold/Ref objects. Keep raw employee/payroll tables restricted to the technical/payroll-administration group.
