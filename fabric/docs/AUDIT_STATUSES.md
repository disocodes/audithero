# Audit statuses

- `CALCULATED` — entitlement calculation had sufficient facts at that grain.
- `COMPLIANT` — actual auditable pay reconciles to expected within tolerance and no review blocker applies.
- `UNDERPAID` — actual auditable pay is below expected beyond tolerance.
- `OVERPAID` — actual auditable pay is above expected beyond tolerance.
- `REQUIRES_REVIEW` — source facts/rule interaction are insufficient for an automatic conclusion.
- `ENTITLEMENT_ONLY` / `ACTUAL_PAY_UNAVAILABLE` — expected entitlement was calculated without usable actual payroll comparison.

Review/instrument findings take precedence over remediation totals.