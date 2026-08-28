# Limitations and validation

AuditHero is deliberately conservative. A review finding is not a compliance result.

## Effective-dated wage coverage

- SACS classification rate packs: July 2022 through July 2026.
- Home Care employee — disability care rate packs: July 2023 through July 2026.
- Other SCHADS wage families require verified packs before automatic wage calculation.

## Overtime

Daily overtime can be repriced automatically where allocation is unambiguous. Full-time work outside a uniquely matched Employment Hero roster can also be repriced. PT/casual weekly 38-hour and fortnightly 76-hour threshold breaches are identified, but overlaps across weekend/public-holiday/shiftwork are review-controlled rather than double-counted.

Cross-midnight overtime allocation is currently `REQUIRES_REVIEW`; ordinary weekend/public-holiday splitting still occurs in the base engine.

## Broken shifts and sleepovers

Broken-shift allowances can be calculated from controlled supplemental facts. The system does not infer a broken shift from gaps alone. Active sleepover work should be supplied as a supplemental event or another separately usable work record.

## Classification and coverage

A current classification is not evidence of a historic classification. AuditHero uses Employment Hero Pay Details history and requires a canonical classification mapping where the tenant label cannot be parsed safely.

## Payroll reconciliation

Only pay categories explicitly mapped as `AUDITABLE_WORK` or `ALLOWANCE` count as actual audited earnings. Leave, reimbursements and unrelated bonuses must not mask an underpayment. Unmapped categories force review.

## Before remediation

Manually reconcile representative employees and pay periods across ordinary work, Saturday/Sunday, public holidays, overtime, sleepovers and broken shifts. Have payroll/industrial-relations specialists validate Award coverage, classifications and interpretation before back-pay or recovery decisions.
