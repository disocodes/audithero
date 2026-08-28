# Historical audit runbook

Do not begin with the entire three-year population.

## Validation sequence

1. **One employee / one pay period** — prove the Employment Hero mapping.
2. **One representative month** — include weekday, Saturday, Sunday, casual/permanent and minimum-engagement cases.
3. **One year** — verify July rule/rate boundaries and employee classification changes.
4. **Full historical range** — only after reconciliation.

Example:

```bash
databricks bundle run historical_audit -- \
  --start_date=2023-07-01 \
  --end_date=2026-06-30 \
  --actual_pay_source=PAYROLL_API
```

The connector automatically chunks timesheet retrieval by month to make a multi-year pull manageable.

## Review order

1. `REQUIRES_REVIEW`
2. `UNDERPAID`
3. `OVERPAID`
4. `COMPLIANT`

Never use a numerical variance for remediation where the same pay period still has a material review flag.

## Re-runs

Runs are append-only. Correct a mapping/rule, re-run the same window, and retain the old `audit_run_id` as evidence of what changed.
