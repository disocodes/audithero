# AuditHero on Databricks

Databricks is a complete deployment target using:

- Unity Catalog / Delta
- notebooks and the shared AuditHero package
- Lakeflow Jobs / Declarative Automation Bundle
- Databricks AI/BI dashboard
- runtime self-tests and readiness analysis

Employment Hero credentials are **optional**.

## File-first mode

After deployment, upload `audithero_input.xlsx` or separate canonical CSV/XLSX files to:

```text
/Volumes/schads_payroll/bronze/landing/input
```

Then run:

```bash
databricks bundle run manual_file_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30
```

The job first runs `02c_file_readiness.py`, then the complete shared SCHADS calculation flow, then refreshes the AI/BI dashboard. No Databricks secrets or Employment Hero API access are used.

Generate a blank workbook with:

```bash
pip install -e .
python tools/build_input_workbook.py --output audithero_input.xlsx
```

## Optional API mode

If automated Employment Hero extraction is desired later:

```bash
./scripts/configure_secrets.sh
databricks bundle run connection_test
databricks bundle run audit_readiness
```

Then use the `historical_audit` or paused `monthly_audit` jobs.

The shared SCHADS engine includes part-time written patterns, rest-after-overtime, meal-break evidence, remote-work aggregation, TOIL, industrial-instrument history, roster/daily/weekly/fortnightly overtime, broken shifts and sleepovers.

See the repository root `README.md`, `QUICKSTART.md` and `docs/` for operating runbooks.
