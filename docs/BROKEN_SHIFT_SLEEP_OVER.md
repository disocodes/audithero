# Broken shifts and sleepovers

AuditHero now infers common SCHADS broken-shift and sleepover structures from separate Employment Hero time records.

## Broken shifts

For disability-services and home-care work, separate same-day work periods with a genuine unpaid gap are grouped as one broken shift. The engine then:

- identifies one or two unpaid breaks;
- applies the applicable broken-shift allowance once per group;
- applies minimum engagement to each work period for PT/casual employees;
- detects more than two unpaid breaks;
- detects spans beyond 12 hours;
- flags two-break groups for agreement verification;
- preserves calculation evidence in `gold.audit_detail`.

Grouping is intentionally conservative. Meal breaks should remain inside a single timesheet record and are not treated as broken-shift gaps.

## Sleepovers

An explicit sleepover work type is the anchor. Adjacent records ending at the sleepover start or beginning at the sleepover end are marked `BEFORE` and `AFTER`.

The engine then:

- applies the sleepover allowance through the base engine;
- checks the minimum work period before/after;
- uses the effective-dated rule pack so the 1 June 2026 sleepover variation does not affect older shifts;
- treats surrounding work as one continuous shift from the 2026 change where applicable;
- checks the 10-hour ordinary threshold or 12-hour written-agreement threshold;
- checks the maximum 8 active hours on either side where the 12-hour agreement applies;
- leaves ambiguous overtime allocation as `REQUIRES_REVIEW` instead of double-counting.

## Operational review

In Payroll, filter `review_flags` for:

- `TWO_BREAK_BROKEN_SHIFT_AGREEMENT_VERIFY`
- `BROKEN_SHIFT_MORE_THAN_TWO_BREAKS`
- `SLEEPOVER_CONTINUOUS_SHIFT_OVERTIME_EXCESS:*`
- `SLEEPOVER_BEFORE_MORE_THAN_8H`
- `SLEEPOVER_AFTER_MORE_THAN_8H`

These are evidence prompts, not automatic compliance failures.
