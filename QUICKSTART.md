# Quickstart

## 1. Prerequisites

- Databricks workspace with Unity Catalog
- Databricks CLI 0.283.0+
- a Databricks SQL warehouse
- Employment Hero OAuth application / HR API access
- optional Employment Hero Payroll API key for actual paid earnings

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
./scripts/deploy.sh
```

## 2. Configure Employment Hero OAuth

Use `tools/eh_oauth_pkce.py`. Employment Hero has announced PKCE as mandatory from 14 September 2026, so use the PKCE helper now rather than building a legacy flow.

```bash
python tools/eh_oauth_pkce.py --client-id ID --client-secret SECRET --redirect-uri https://approved/callback
```

Complete the browser authorisation, then exchange the code using the printed verifier. Store only the refresh token in Databricks Secrets.

## 3. Configure secrets

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

## 4. Activate mappings

```bash
cp config/classification_mapping.example.json config/classification_mapping.json
cp config/work_type_mapping.example.json config/work_type_mapping.json
cp config/work_location_state_mapping.example.json config/work_location_state_mapping.json
cp config/employee_overrides.example.json config/employee_overrides.json
cp config/pay_category_mapping.example.json config/pay_category_mapping.json
```

Edit them using values from your Employment Hero tenant.

## 5. Test connection

```bash
databricks bundle run connection_test
```

## 6. Run one validation month

```bash
databricks bundle run historical_audit -- \
  --start_date=2026-07-01 \
  --end_date=2026-07-31 \
  --actual_pay_source=PAYROLL_API
```

Reconcile representative cases manually before going back multiple years.

## 7. Three-year historical audit

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

## 8. Monthly payroll

The monthly job is deployed **PAUSED**. After validation, open **Workflows → AuditHero - Monthly Payroll Audit**, review the schedule and unpause it. The default is 09:00 on the 25th in Australia/Perth and uses a 45-day lookback.
