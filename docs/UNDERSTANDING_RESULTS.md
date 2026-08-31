# Understanding AuditHero results

AuditHero separates expected entitlement calculation from actual-pay reconciliation and from evidence review.

## Pay-period statuses

### COMPLIANT

Actual auditable pay is within the configured tolerance of expected auditable pay for the period, and no unresolved entitlement evidence prevents the conclusion.

### UNDERPAID

Confirmed auditable pay is below the calculated expected amount by more than the tolerance.

### OVERPAID

Confirmed auditable pay is above expected auditable pay by more than the tolerance.

### REQUIRES_REVIEW

AuditHero has identified a condition it cannot safely resolve from the supplied evidence. Examples include ambiguous roster matching, unresolved industrial-instrument coverage, cross-midnight allocation ambiguity or missing agreement evidence.

`REQUIRES_REVIEW` is not the same as an underpayment. Review items are intentionally excluded from headline confirmed remediation totals until resolved.

### ACTUAL_PAY_UNAVAILABLE

Expected entitlement was calculated, but usable actual payroll earnings were not supplied or could not be mapped into auditable pay.

## Expected pay

Expected pay is produced from the effective-dated rule library and the employee/shift facts supplied to the engine. Calculation evidence is retained at detail/event level so a reviewer can see which rate/multiplier/allowance logic was applied.

## Actual auditable pay

Actual auditable pay comes from payroll earnings after pay-category treatment. Review this mapping carefully: including or excluding the wrong earnings category can make reconciliation misleading even when the entitlement engine is correct.

## Variance

The reconciliation variance is the difference between actual auditable pay and expected auditable pay. Always interpret it together with status and review findings.

## Dashboard review order

A practical review sequence is:

1. **Overview:** audit period, employees, expected/actual amounts and status counts.
2. **Exceptions:** underpaid/overpaid/review periods.
3. **Shift evidence:** inspect detailed worked periods, classification/rate and calculation evidence.
4. **Supplemental / TOIL:** review event-based adjustments.
5. **Controls / rules:** confirm rule versions, readiness and evidence coverage.

## What to do with REQUIRES_REVIEW

For each review item:

1. identify the missing/ambiguous fact;
2. obtain the source evidence;
3. update the canonical data/control register or mapping;
4. rerun the affected period; and
5. keep an audit trail of the change.

Do not manually overwrite AuditHero outputs to make a review item appear compliant.

## Remediation decisions

Before remediation, independently confirm at least:

- Award/industrial instrument coverage;
- classification history;
- employment type history;
- representative rule calculations;
- pay-category treatment; and
- whether unresolved review items could materially change the result.
