# AuditHero quickstart

## 1. Prerequisites

- Databricks workspace with Unity Catalog
- Databricks CLI 0.283.0 or newer
- Databricks SQL warehouse
- Employment Hero HR API access / OAuth application
- optional Employment Hero Payroll API key for actual-pay reconciliation

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
export DATABRICKS_BUNDLE_VAR_accounts_email="accounts-user@your-company.example"
```

## 2. Deploy

```bash
./scripts/deploy.sh
```

This creates the catalog, rule tables, jobs and AI/BI dashboard. The monthly schedule remains PAUSED.

## 3. Configure Employment Hero

Use `tools/eh_oauth_pkce.py` for initial OAuth, then:

```bash
./scripts/configure_secrets.sh
```

Required: `EH_ORGANISATION_ID`, `EH_HR_CLIENT_ID`, `EH_HR_CLIENT_SECRET`, `EH_HR_REFRESH_TOKEN`. Optional actual-pay reconciliation uses `EH_PAYROLL_API_KEY` and `EH_PAYROLL_BUSINESS_ID`.

## 4. Activate tenant mappings

```bash
cp config/classification_mapping.example.json config/classification_mapping.json
cp config/work_type_mapping.example.json config/work_type_mapping.json
cp config/work_location_state_mapping.example.json config/work_location_state_mapping.json
cp config/employee_overrides.example.json config/employee_overrides.json
cp config/pay_category_mapping.example.json config/pay_category_mapping.json
```

## 5. Test connectivity

```bash
databricks bundle run connection_test
```

## 6. Run readiness analysis

```bash
databricks bundle run audit_readiness
```

The readiness job inspects your real Employment Hero classification, pay-category, work-type and work-location metadata and writes `ops.readiness_findings`. Resolve `MAPPING_REQUIRED` items before relying on a historical remediation total.

## 7. Validate one month

```bash
databricks bundle run historical_audit -- \
  --start_date=2026-07-01 \
  --end_date=2026-07-31 \
  --actual_pay_source=PAYROLL_API
```

Review `REQUIRES_REVIEW` first and manually reconcile representative cases.

## 8. Optional supplemental facts

For on-call, recall, active sleepover work and other facts not represented by ordinary timesheets, load `config/supplemental_events.example.csv` as:

`/Volumes/schads_payroll/bronze/landing/supplemental_events.csv`

## 9. Run three-year audit

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

SACS and Home Care disability rate packs cover this complete window.

## 10. Enable monthly payroll workflow

Open **Workflows → AuditHero - Monthly Payroll Audit**, verify the lookback and Accounts subscriber, then unpause the schedule. Each successful run refreshes and emails the AI/BI dashboard snapshot.
