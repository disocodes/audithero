# AuditHero quickstart

Choose **Microsoft Fabric** or **Databricks**. Both run the same SCHADS engine and support two ingestion modes:

- **FILES** — upload CSV/XLSX data; no Employment Hero credentials required.
- **API** — connect directly to Employment Hero HR/Payroll for automated extraction.

For an initial deployment, **FILES is the simplest path** and is the recommended way to validate the engine against a known pay period before enabling API automation.

## Build the optional Excel input template

From the repository:

```bash
pip install -e .
python tools/build_input_workbook.py --output audithero_input.xlsx
```

The workbook contains these sheets:

```text
employees              required
pay_details            required
employment_history     required
timesheets             required
rostered_shifts        recommended
payroll_earnings       optional for actual-vs-expected
pay_runs               optional
```

You can instead use separate files named `employees.csv`, `timesheets.xlsx`, etc.

---

## Microsoft Fabric — file-first setup

Prerequisites:

- Microsoft Fabric workspace/capacity
- Azure CLI or `FABRIC_ACCESS_TOKEN`

**Azure Key Vault and Employment Hero credentials are optional.** They are needed only for API mode.

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
# set workspace_id; key_vault_url may remain blank
az login
./fabric/scripts/deploy.sh
```

The installer creates:

- schema-enabled Lakehouse
- Fabric Runtime 2.0 Environment
- AuditHero wheel + SCHADS rule packs
- setup/self-test notebooks
- file audit notebook + `AuditHero - Uploaded Files Audit Pipeline`
- optional Employment Hero API notebooks/pipelines
- disabled monthly API schedule
- Direct Lake snapshot tables
- semantic model
- Power BI report

### Upload files

Upload either:

```text
Files/input/audithero_input.xlsx
```

or separate canonical CSV/XLSX files into:

```text
Files/input/
```

Then run the Fabric pipeline:

```text
AuditHero - Uploaded Files Audit Pipeline
```

Set the date range you want to audit. No Key Vault configuration is required for this workflow.

If you later want automated Employment Hero extraction, configure Azure Key Vault using `fabric/docs/KEY_VAULT.md` and use the API historical/monthly pipelines.

---

## Databricks — file-first setup

Prerequisites:

- Databricks workspace with Unity Catalog
- Databricks CLI 0.283.0+
- SQL warehouse

Employment Hero API access is optional.

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
export DATABRICKS_BUNDLE_VAR_accounts_email="accounts-user@your-company.example"
./scripts/deploy.sh
```

The setup creates the default input Volume path:

```text
/Volumes/schads_payroll/bronze/landing/input
```

Upload `audithero_input.xlsx` or separate canonical files there, then run:

```bash
databricks bundle run manual_file_audit -- \
  --start_date=2026-07-01 \
  --end_date=2026-07-31
```

For a three-year file audit:

```bash
databricks bundle run manual_file_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30
```

The job refreshes the Databricks dashboard after the audit.

### Optional Employment Hero API mode

Only if you want automated extraction:

```bash
./scripts/configure_secrets.sh
databricks bundle run connection_test
databricks bundle run audit_readiness
```

Then use `historical_audit` or the paused `monthly_audit` job.

---

## Controlled compliance registers

Both ingestion modes use the same controlled evidence. Create/populate these where applicable:

```text
industrial_instrument_history.csv
part_time_patterns.csv
part_time_variations.csv
public_holiday_overrides.csv
overtime_rest_controls.csv
meal_break_events.csv
supplemental_events.csv
toil_register.csv
```

Version-controlled `.example` files are in `config/`.

For historical remediation, `industrial_instrument_history.csv` is especially important because classification alone does not prove that SCHADS rather than an enterprise agreement/IFA applied at the time.

## Recommended validation sequence

```text
Deploy
  ↓
Run platform self-test
  ↓
Upload one known payroll period
  ↓
Run FILES audit
  ↓
Compare representative employees manually
  ↓
Resolve REQUIRES_REVIEW
  ↓
Run multi-year audit
  ↓
Optionally configure Employment Hero API
  ↓
Enable recurring monthly automation
```

Do not use headline remediation totals until unresolved review items, historical instrument coverage, classifications, locations/public holidays and payroll-category treatment have been validated.
