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
# Defaults to the deployer if omitted.
export DATABRICKS_BUNDLE_VAR_accounts_email="accounts-user@your-company.example"
```

## 2. Deploy the Databricks resources

```bash
./scripts/deploy.sh
```

This creates the Unity Catalog objects, effective-dated reference tables, jobs and AI/BI dashboard. The monthly schedule remains PAUSED.

## 3. Configure Employment Hero OAuth and secrets

Use `tools/eh_oauth_pkce.py` for the initial OAuth flow, then:

```bash
./scripts/configure_secrets.sh
```

Required HR secrets:

```text
EH_ORGANISATION_ID
EH_HR_CLIENT_ID
EH_HR_CLIENT_SECRET
EH_HR_REFRESH_TOKEN
```

Optional actual-pay secrets:

```text
EH_PAYROLL_API_KEY
EH_PAYROLL_BUSINESS_ID
```

## 4. Activate tenant mappings

```bash
cp config/classification_mapping.example.json config/classification_mapping.json
cp config/work_type_mapping.example.json config/work_type_mapping.json
cp config/work_location_state_mapping.example.json config/work_location_state_mapping.json
cp config/employee_overrides.example.json config/employee_overrides.json
cp config/pay_category_mapping.example.json config/pay_category_mapping.json
```

Complete the mappings with values from your tenant.

## 5. Test the API

```bash
databricks bundle run connection_test
```

## 6. Validate one month

```bash
databricks bundle run historical_audit -- \
  --start_date=2026-07-01 \
  --end_date=2026-07-31 \
  --actual_pay_source=PAYROLL_API
```

Review `REQUIRES_REVIEW` first. Manually reconcile representative ordinary, weekend, overtime, public-holiday and sleepover cases.

## 7. Optional supplemental facts

For facts not represented by ordinary timesheets, copy the example header into the Unity Catalog Volume:

```text
/Volumes/schads_payroll/bronze/landing/supplemental_events.csv
```

See `docs/SUPPLEMENTAL_EVENTS.md`.

## 8. Run historical audit

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

## 9. Enable monthly payroll workflow

Open **Workflows → AuditHero - Monthly Payroll Audit**. Verify the 45-day lookback and dashboard subscriber, then unpause the schedule.

After every successful monthly audit, the job refreshes the AuditHero AI/BI dashboard and emails a dashboard snapshot to `${var.accounts_email}` as configured at deployment.
