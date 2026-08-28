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

## 2. Deploy and self-test

```bash
./scripts/deploy.sh
```

Deployment now performs three things automatically:

1. validates and deploys the Databricks bundle;
2. creates/updates the AuditHero catalog, rule tables, jobs and AI/BI dashboard;
3. runs **AuditHero - Self Test** inside Databricks.

The self-test checks representative historical rates, Saturday casual pay, sleepover allowance-only treatment, location-specific public holidays, broken-shift grouping and period-overtime repricing. A failed self-test stops deployment.

The monthly schedule remains PAUSED.

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
cp config/public_holiday_overrides.example.csv config/public_holiday_overrides.csv
```

For each Employment Hero work location, configure at least `state`. If a location can have local public holidays, also set `holiday_location_key`.

Example:

```json
{
  "employment-hero-location-id": {
    "state": "WA",
    "holiday_location_key": "KUNUNURRA"
  }
}
```

## 5. Test connectivity

```bash
databricks bundle run connection_test
```

## 6. Run readiness analysis

```bash
databricks bundle run audit_readiness
```

The readiness job inspects your real Employment Hero classification, pay-category, work-type and work-location metadata and writes `ops.readiness_findings`. Resolve `MAPPING_REQUIRED` items before relying on a historical remediation total. Review `MAPPING_RECOMMENDED` location items where local public-holiday handling may matter.

## 7. Validate one month

```bash
databricks bundle run historical_audit -- \
  --start_date=2026-07-01 \
  --end_date=2026-07-31 \
  --actual_pay_source=PAYROLL_API
```

Review `REQUIRES_REVIEW` first and manually reconcile representative cases, including at least one weekend shift, one casual shift, one overtime example and—if used in your organisation—one sleepover/broken-shift example.

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

Recommended payroll sequence:

```text
Timesheets approved
  -> draft pay run available
  -> AuditHero monthly audit
  -> review REQUIRES_REVIEW
  -> correct confirmed payroll issues
  -> rerun AuditHero
  -> finalise payroll
```
