# AuditHero — SCHADS payroll compliance

AuditHero is a production-oriented payroll audit system for the **Social, Community, Home Care and Disability Services Industry Award (SCHADS / MA000100)**. It reconstructs historical Award entitlements with effective-dated rules, reconciles expected versus actual payroll and supports both ongoing payroll assurance and multi-year remediation audits.

The repository ships **two first-class deployments**:

- **Microsoft Fabric** — schema-enabled Lakehouse, Runtime Environment, Fabric notebooks, Data Factory pipelines, Direct Lake semantic model and Power BI report.
- **Databricks** — Unity Catalog/Delta, notebooks, Declarative Automation Bundle jobs and Databricks AI/BI dashboard.

Both platforms use the **same `schads_audit` Python engine and the same source-controlled `rules/MA000100` JSON library**.

## Data sources: API is optional

AuditHero supports two equally valid ingestion paths:

### FILES — simplest / no credentials

Upload either:

```text
audithero_input.xlsx
```

with canonical sheets, or separate files such as:

```text
employees.csv
pay_details.csv
employment_history.csv
timesheets.csv
rostered_shifts.csv
payroll_earnings.csv
```

CSV and Excel can be mixed. Employment Hero credentials are **not required**.

Generate a blank workbook with:

```bash
pip install -e .
python tools/build_input_workbook.py --output audithero_input.xlsx
```

### API — optional automation

Employment Hero HR/Payroll APIs can be enabled later for direct historical extraction and recurring monthly runs. Fabric uses Azure Key Vault; Databricks uses Databricks Secrets.

This lets you validate the complete audit engine using exported payroll/timesheet data before granting API access.

## Shared calculation coverage

The engine covers effective-dated SACS and Home Care disability-care rates, classification/employment history, casual loading, weekends/public holidays/shiftwork, minimum engagement, roster and period overtime, broken shifts, sleepovers, part-time written patterns, rest-after-overtime, meal events, on-call/recall/remote/higher-duty events, TOIL, industrial-instrument history and actual-versus-expected pay-period reconciliation. Ambiguous or incomplete evidence produces `REQUIRES_REVIEW` rather than a guessed result.

## Microsoft Fabric

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
# edit workspace_id; key_vault_url can remain blank for FILES mode
az login
./fabric/scripts/deploy.sh
```

The installer creates/updates the Lakehouse, Runtime 2.0 Environment, AuditHero wheel, self-tests, uploaded-file readiness/audit pipeline, optional Employment Hero API pipelines, Direct Lake semantic model and Power BI report.

For FILES mode upload data to:

```text
Lakehouse / Files / input /
```

and run:

```text
AuditHero - Uploaded Files Audit Pipeline
```

Azure Key Vault is only required if you choose API mode.

See `fabric/docs/DEPLOYMENT.md` and `QUICKSTART.md`.

## Databricks

```bash
databricks auth login --host https://<workspace>
export DATABRICKS_BUNDLE_VAR_sql_warehouse_id="<warehouse-id>"
./scripts/deploy.sh
```

The bundle deploys setup/self-test jobs, the credential-free `manual_file_audit` job, optional Employment Hero API jobs and the Databricks AI/BI dashboard.

Default FILES path:

```text
/Volumes/schads_payroll/bronze/landing/input
```

Run:

```bash
databricks bundle run manual_file_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30
```

Only run `./scripts/configure_secrets.sh` if you want API mode.

## Recommended operating sequence

```text
Deploy
  -> platform self-test
  -> upload a known payroll period
  -> file-readiness validation
  -> FILES audit
  -> manually validate representative calculations
  -> resolve REQUIRES_REVIEW
  -> run multi-year historical audit
  -> optionally enable Employment Hero API automation
  -> enable recurring monthly workflow
```

## Rule source of truth

`rules/MA000100/` contains effective-dated rate, condition and allowance packs. Add new Fair Work versions there, record the source, add regression tests and redeploy. Do not fork Award logic separately for Fabric and Databricks.

AuditHero is compliance-engineering software, not legal advice. Independently validate Award coverage, classifications, industrial-instrument history and representative calculations before remediation or recovery decisions.
