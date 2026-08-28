# Historical audit on Fabric

## Recommended sequence

1. Connection test.
2. Readiness scan.
3. One employee / one known pay period.
4. One representative month.
5. Test an annual rate boundary and the June 2026 sleepover boundary.
6. Twelve months.
7. Full historical range.

The historical pipeline accepts `start_date`, `end_date` and `actual_pay_source` and invokes the parameterised historical notebook.

For a three-year example:

```text
start_date = 2023-07-01
end_date   = 2026-06-30
actual_pay_source = PAYROLL_API
```

## Review order

1. `INSTRUMENT_REVIEW` / enterprise agreement / IFA findings.
2. `REQUIRES_REVIEW`.
3. `UNDERPAID`.
4. `OVERPAID`.
5. `COMPLIANT`.

Do not establish a remediation amount from records that still require review.

## Historical evidence registers

Use `Files/config` for controlled historical evidence that cannot be reconstructed reliably from current Employment Hero fields:

- industrial-instrument history
- part-time written patterns and variations
- local public-holiday overrides
- meal-break events
- overtime/rest controls
- supplemental events
- TOIL register

The audit run is append-only and identified by `audit_run_id`; Power BI uses materialised latest-successful snapshots.